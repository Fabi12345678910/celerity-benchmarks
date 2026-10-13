// linkbw: CPU <-> GPU transfer limits without Celerity or copylib: DMA copies between pinned host memory and device memory, and a
// GPU kernel that reads or writes pinned host memory directly (the path of COPYLIB_HOST_KERNEL=1), contiguous or strided as in
// strided_transfer (4 useful bytes per row of M * 4 bytes).
//
// Usage: linkbw <test> <MiB> [reps=5] [load]
//   test   dma_h2d, dma_d2h      hipMemcpyAsync of MiB between pinned host memory (hipHostMalloc) and device memory
//          dma_bidir             both at the same time on two streams (GB/s: both directions together)
//          kernel_read           kernel copies MiB from host memory to device memory, 16-byte accesses
//          kernel_write          kernel copies MiB from device memory to host memory, 16-byte accesses
//          kernel_read_s2/_s4    kernel reads 4 bytes from every row of 8/16 bytes in host memory (M = 2/4), writes them contiguously
//          kernel_write_s2/_s4   kernel writes 4 bytes into every row of 8/16 bytes in host memory, from contiguous device memory
//   MiB    useful bytes per copy (strided: the packed side; the host side is M times larger)
//   load   none, or <pack2|pack4|unpack2|unpack4>:<cpus>: pinned CPU threads (one per listed CPU) run copylib's staging pack/unpack
//          loop on their own 64 MiB buffers during the whole measurement, as the workers of a staged copy do next to its DMA
//          copies; printed as "load: <GB/s>GB/s" (useful bytes, averaged over the measured reps)
// Output: "<test>: <GB/s>GB/s" (median of reps after one warmup, useful bytes / kernel or copy time from HIP events).
// HSA_ENABLE_SDMA=0 in the environment makes the DMA copies use blit kernels instead of the SDMA engines.
#include <hip/hip_runtime.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

#include <pthread.h>
#include <sched.h>
#if !defined(__HIP_DEVICE_COMPILE__)
#include <emmintrin.h>
#define STREAM32(p, v) _mm_stream_si32(p, v)
#define SFENCE() _mm_sfence()
#else // the device pass only parses the host code
#define STREAM32(p, v) (*(p) = (v))
#define SFENCE()
#endif

#define CHECK(x)                                                                                                                      \
	do {                                                                                                                              \
		hipError_t e = (x);                                                                                                           \
		if(e != hipSuccess) {                                                                                                         \
			std::fprintf(stderr, "%s failed: %s\n", #x, hipGetErrorString(e));                                                       \
			std::exit(1);                                                                                                             \
		}                                                                                                                             \
	} while(0)

__global__ void copy16(const uint4* __restrict__ s, uint4* __restrict__ d, size_t n) {
	for(size_t i = blockIdx.x * size_t(blockDim.x) + threadIdx.x; i < n; i += size_t(gridDim.x) * blockDim.x) d[i] = s[i];
}

// strided -> contiguous (read host rows) or contiguous -> strided (write host rows); n rows of 4 bytes, pitch m * 4 bytes
__global__ void gather(const uint32_t* __restrict__ s, uint32_t* __restrict__ d, size_t n, int m) {
	for(size_t i = blockIdx.x * size_t(blockDim.x) + threadIdx.x; i < n; i += size_t(gridDim.x) * blockDim.x) d[i] = s[i * m];
}
__global__ void scatter(const uint32_t* __restrict__ s, uint32_t* __restrict__ d, size_t n, int m) {
	for(size_t i = blockIdx.x * size_t(blockDim.x) + threadIdx.x; i < n; i += size_t(gridDim.x) * blockDim.x) d[i * m] = s[i];
}

// background CPU load: copylib's pack (4-byte loads from rows, non-temporal stores) or unpack (contiguous loads, 4-byte stores into rows)
struct cpu_load {
	std::atomic<bool> stop{false};
	std::atomic<uint64_t> bytes{0};
	std::vector<std::thread> threads;

	void start(const std::string& spec) {
		const auto colon = spec.find(':');
		const std::string kind = spec.substr(0, colon);
		const bool pack = kind.rfind("pack", 0) == 0;
		const size_t pitch = kind.back() == '2' ? 8 : 16;
		std::vector<int> cpus;
		for(const char* p = spec.c_str() + colon + 1; *p;) {
			cpus.push_back(std::atoi(p));
			while(*p && *p != ',') ++p;
			if(*p == ',') ++p;
		}
		std::atomic<int> ready{0};
		for(int cpu : cpus) {
			threads.emplace_back([this, cpu, pack, pitch, &ready] {
				cpu_set_t set;
				CPU_ZERO(&set);
				CPU_SET(cpu, &set);
				pthread_setaffinity_np(pthread_self(), sizeof(set), &set);
				const size_t n = size_t(64) << 20; // useful bytes per pass
				auto* strided = static_cast<std::byte*>(std::aligned_alloc(4096, n / 4 * pitch));
				auto* packed = static_cast<std::byte*>(std::aligned_alloc(4096, n));
				std::memset(strided, 1, n / 4 * pitch);
				std::memset(packed, 1, n);
				++ready;
				while(!stop) {
					const std::byte* s = strided;
					std::byte* c = packed;
					if(pack) {
						for(size_t r = 0; r < n / 4; ++r, s += pitch, c += 4) {
							int v;
							std::memcpy(&v, s, 4);
							STREAM32(reinterpret_cast<int*>(c), v);
						}
						SFENCE();
					} else {
						std::byte* d = strided;
						const std::byte* p = packed;
						for(size_t r = 0; r < n / 4; ++r, d += pitch, p += 4) std::memcpy(d, p, 4);
					}
					bytes += n;
				}
				std::free(strided);
				std::free(packed);
			});
		}
		while(ready < static_cast<int>(cpus.size())) std::this_thread::yield();
	}
	~cpu_load() {
		stop = true;
		for(auto& t : threads) t.join();
	}
};

int main(int argc, char** argv) {
	if(argc < 3) {
		std::fprintf(stderr, "usage: %s <test> <MiB> [reps]\n", argv[0]);
		return 1;
	}
	const std::string test = argv[1];
	const size_t bytes = static_cast<size_t>(std::atoll(argv[2])) << 20;
	const int reps = argc > 3 ? std::atoi(argv[3]) : 5;
	const int m = test.size() > 3 && test[test.size() - 3] == '_' && test[test.size() - 2] == 's' ? test.back() - '0' : 1;

	void *host, *host2 = nullptr, *dev, *dev2 = nullptr;
	CHECK(hipHostMalloc(&host, bytes * m, hipHostMallocDefault));
	std::memset(host, 1, bytes * m);
	CHECK(hipMalloc(&dev, bytes));
	CHECK(hipMemset(dev, 2, bytes));
	if(test == "dma_bidir") {
		CHECK(hipHostMalloc(&host2, bytes, hipHostMallocDefault));
		std::memset(host2, 1, bytes);
		CHECK(hipMalloc(&dev2, bytes));
		CHECK(hipMemset(dev2, 2, bytes));
	}
	hipStream_t s1, s2;
	CHECK(hipStreamCreate(&s1));
	CHECK(hipStreamCreate(&s2));
	hipEvent_t start, stop, stop2;
	CHECK(hipEventCreate(&start));
	CHECK(hipEventCreate(&stop));
	CHECK(hipEventCreate(&stop2));

	const size_t rows = bytes / 4;
	const unsigned block = 256;
	const unsigned grid = 4096;
	const auto launch = [&] {
		if(test == "dma_h2d") {
			CHECK(hipMemcpyAsync(dev, host, bytes, hipMemcpyHostToDevice, s1));
		} else if(test == "dma_d2h") {
			CHECK(hipMemcpyAsync(host, dev, bytes, hipMemcpyDeviceToHost, s1));
		} else if(test == "dma_bidir") {
			CHECK(hipMemcpyAsync(dev, host, bytes, hipMemcpyHostToDevice, s1));
			CHECK(hipMemcpyAsync(host2, dev2, bytes, hipMemcpyDeviceToHost, s2));
		} else if(test == "kernel_read") {
			copy16<<<grid, block, 0, s1>>>(static_cast<const uint4*>(host), static_cast<uint4*>(dev), bytes / 16);
		} else if(test == "kernel_write") {
			copy16<<<grid, block, 0, s1>>>(static_cast<const uint4*>(dev), static_cast<uint4*>(host), bytes / 16);
		} else if(test.rfind("kernel_read_s", 0) == 0) {
			gather<<<grid, block, 0, s1>>>(static_cast<const uint32_t*>(host), static_cast<uint32_t*>(dev), rows, m);
		} else if(test.rfind("kernel_write_s", 0) == 0) {
			scatter<<<grid, block, 0, s1>>>(static_cast<const uint32_t*>(dev), static_cast<uint32_t*>(host), rows, m);
		} else {
			std::fprintf(stderr, "unknown test %s\n", test.c_str());
			std::exit(1);
		}
		CHECK(hipGetLastError());
	};

	const std::string load_spec = argc > 4 ? argv[4] : "none";
	cpu_load load;
	if(load_spec != "none") load.start(load_spec);
	uint64_t load_bytes0 = 0;
	std::chrono::steady_clock::time_point load_t0;

	std::vector<double> gbps;
	for(int r = 0; r <= reps; ++r) { // rep 0: warmup
		if(r == 1) {
			load_bytes0 = load.bytes;
			load_t0 = std::chrono::steady_clock::now();
		}
		CHECK(hipDeviceSynchronize());
		CHECK(hipEventRecord(start, s1));
		if(test == "dma_bidir") CHECK(hipStreamWaitEvent(s2, start, 0));
		launch();
		CHECK(hipEventRecord(stop, s1));
		CHECK(hipEventRecord(stop2, s2));
		CHECK(hipEventSynchronize(stop));
		CHECK(hipEventSynchronize(stop2));
		float ms = 0, ms2 = 0;
		CHECK(hipEventElapsedTime(&ms, start, stop));
		CHECK(hipEventElapsedTime(&ms2, start, stop2));
		const double moved = test == "dma_bidir" ? 2.0 * bytes : 1.0 * bytes;
		if(r > 0) gbps.push_back(moved / (std::max(ms, test == "dma_bidir" ? ms2 : 0.f) * 1e-3) / 1e9);
	}
	const double load_gbps = (load.bytes - load_bytes0) / std::chrono::duration<double>(std::chrono::steady_clock::now() - load_t0).count() / 1e9;
	std::sort(gbps.begin(), gbps.end());
	hipDeviceProp_t prop;
	CHECK(hipGetDeviceProperties(&prop, 0));
	const char* sdma = std::getenv("HSA_ENABLE_SDMA");
	std::printf("linkbw %s MiB=%zu device=%s SDMA=%s load=%s\n", test.c_str(), bytes >> 20, prop.gcnArchName, sdma ? sdma : "default",
	    load_spec.c_str());
	std::printf("%s: %.3fGB/s\n", test.c_str(), gbps[gbps.size() / 2]);
	if(load_spec != "none") std::printf("load: %.3fGB/s\n", load_gbps);
	return 0;
}
