// membw: host memory bandwidth with the access patterns of copylib's staging, on pinned threads (no GPU involved).
//
// Usage: membw <test> <cpus> <local|first> [MiB per thread=64] [reps=5]
//   test   read      64-bit loads (sum)
//          write     regular 16-byte stores (each line is read before it is written: write-allocate)
//          write_nt  non-temporal 16-byte stores (no read of the line)
//          copy      16-byte loads + regular stores
//          copy_nt   16-byte loads + non-temporal stores
//          pack2     staging pack as in copylib 014e21a: 4-byte loads from rows of 8 bytes, non-temporal 4-byte stores (M = 2)
//          pack4     the same with rows of 16 bytes (M = 4)
//          unpack2   staging unpack as in copylib: contiguous 4-byte loads, regular 4-byte stores into rows of 8 bytes (M = 2)
//          unpack4   the same with rows of 16 bytes (M = 4)
//   cpus   comma-separated CPU list, one thread per entry, thread i pinned to the i-th CPU
//   local  each thread first-touches its own buffers (memory on its own NUMA node)
//   first  all buffers are first-touched by a thread on the first CPU (one NUMA node, like the data of a staged copy)
// Each thread works on its own part. Bytes per thread: MiB of useful data (pack/unpack: the packed side; the strided side is M times larger).
// Output (median of reps): "useful: <GB/s>GB/s" = bytes delivered by the operation (read: read, write: written, copy/pack/unpack:
// copied), and "memory: <GB/s>GB/s" = modeled memory traffic incl. write-allocate reads (read 1, write 2, write_nt 1, copy 3,
// copy_nt 2, packM M+1, unpackM 2M+1 bytes per useful byte).
#include <algorithm>
#include <atomic>
#include <barrier>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

#include <emmintrin.h>
#include <pthread.h>
#include <sched.h>

namespace {

void pin(int cpu) {
	cpu_set_t set;
	CPU_ZERO(&set);
	CPU_SET(cpu, &set);
	pthread_setaffinity_np(pthread_self(), sizeof(set), &set);
}

std::byte* alloc_touch(size_t bytes) {
	auto* p = static_cast<std::byte*>(std::aligned_alloc(4096, (bytes + 4095) / 4096 * 4096));
	if(!p) {
		std::fprintf(stderr, "allocation of %zu bytes failed\n", bytes);
		std::exit(1);
	}
	std::memset(p, 1, bytes);
	return p;
}

std::atomic<uint64_t> sink{0};

// n: useful bytes of this thread; src/dst: its buffers
void run(const std::string& t, std::byte* src, std::byte* dst, size_t n) {
	if(t == "read") {
		const auto* s = reinterpret_cast<const uint64_t*>(src);
		uint64_t a = 0, b = 0, c = 0, d = 0;
		for(size_t i = 0; i < n / 8; i += 4) {
			a += s[i];
			b += s[i + 1];
			c += s[i + 2];
			d += s[i + 3];
		}
		sink += a + b + c + d;
	} else if(t == "write" || t == "write_nt") {
		auto* d = reinterpret_cast<__m128i*>(dst);
		const __m128i v = _mm_set1_epi32(7);
		if(t == "write") {
			for(size_t i = 0; i < n / 16; ++i) _mm_store_si128(d + i, v);
		} else {
			for(size_t i = 0; i < n / 16; ++i) _mm_stream_si128(d + i, v);
			_mm_sfence();
		}
	} else if(t == "copy" || t == "copy_nt") {
		const auto* s = reinterpret_cast<const __m128i*>(src);
		auto* d = reinterpret_cast<__m128i*>(dst);
		if(t == "copy") {
			for(size_t i = 0; i < n / 16; ++i) _mm_store_si128(d + i, _mm_load_si128(s + i));
		} else {
			for(size_t i = 0; i < n / 16; ++i) _mm_stream_si128(d + i, _mm_load_si128(s + i));
			_mm_sfence();
		}
	} else if(t == "pack2" || t == "pack4") {
		const size_t pitch = t == "pack2" ? 8 : 16;
		const std::byte* s = src;
		std::byte* c = dst;
		for(size_t r = 0; r < n / 4; ++r, s += pitch, c += 4) {
			int v;
			std::memcpy(&v, s, 4);
			_mm_stream_si32(reinterpret_cast<int*>(c), v);
		}
		_mm_sfence();
	} else if(t == "unpack2" || t == "unpack4") {
		const size_t pitch = t == "unpack2" ? 8 : 16;
		const std::byte* c = src;
		std::byte* s = dst;
		for(size_t r = 0; r < n / 4; ++r, s += pitch, c += 4) std::memcpy(s, c, 4);
	} else {
		std::fprintf(stderr, "unknown test %s\n", t.c_str());
		std::exit(1);
	}
}

// bytes of the source and destination buffer per useful byte
std::pair<size_t, size_t> sides(const std::string& t) {
	if(t == "read") return {1, 0};
	if(t == "write" || t == "write_nt") return {0, 1};
	if(t == "copy" || t == "copy_nt") return {1, 1};
	if(t == "pack2") return {2, 1};
	if(t == "pack4") return {4, 1};
	if(t == "unpack2") return {1, 2};
	return {1, 4}; // unpack4
}

double traffic(const std::string& t) {
	if(t == "read" || t == "write_nt") return 1;
	if(t == "write" || t == "copy_nt") return 2;
	if(t == "copy") return 3;
	if(t == "pack2") return 3;
	if(t == "pack4") return 5;
	if(t == "unpack2") return 5;
	return 9; // unpack4
}

} // namespace

int main(int argc, char** argv) {
	if(argc < 4) {
		std::fprintf(stderr, "usage: %s <test> <cpus> <local|first> [MiB per thread] [reps]\n", argv[0]);
		return 1;
	}
	const std::string test = argv[1];
	std::vector<int> cpus;
	for(const char* p = argv[2]; *p;) {
		cpus.push_back(std::atoi(p));
		while(*p && *p != ',') ++p;
		if(*p == ',') ++p;
	}
	const bool first = std::string(argv[3]) == "first";
	const size_t n = static_cast<size_t>(argc > 4 ? std::atoll(argv[4]) : 64) << 20;
	const int reps = argc > 5 ? std::atoi(argv[5]) : 5;
	const int threads = static_cast<int>(cpus.size());
	const auto [src_f, dst_f] = sides(test);

	std::vector<std::byte*> src(threads, nullptr), dst(threads, nullptr);
	if(first) {
		std::thread([&] {
			pin(cpus[0]);
			for(int i = 0; i < threads; ++i) {
				if(src_f) src[i] = alloc_touch(n * src_f);
				if(dst_f) dst[i] = alloc_touch(n * dst_f);
			}
		}).join();
	}

	std::vector<double> times;
	std::chrono::steady_clock::time_point t0;
	std::barrier start(threads + 1), done(threads + 1);
	std::vector<std::thread> pool;
	for(int i = 0; i < threads; ++i) {
		pool.emplace_back([&, i] {
			pin(cpus[i]);
			if(!first) {
				if(src_f) src[i] = alloc_touch(n * src_f);
				if(dst_f) dst[i] = alloc_touch(n * dst_f);
			}
			for(int r = 0; r <= reps; ++r) { // rep 0: warmup
				start.arrive_and_wait();
				run(test, src[i], dst[i], n);
				done.arrive_and_wait();
			}
		});
	}
	for(int r = 0; r <= reps; ++r) {
		start.arrive_and_wait();
		t0 = std::chrono::steady_clock::now();
		done.arrive_and_wait();
		if(r > 0) times.push_back(std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count());
	}
	for(auto& t : pool) t.join();

	std::sort(times.begin(), times.end());
	const double s = times[times.size() / 2];
	const double useful = static_cast<double>(n) * threads / s / 1e9;
	std::printf("membw %s threads=%d place=%s MiB/thread=%zu\n", test.c_str(), threads, first ? "first" : "local", n >> 20);
	std::printf("useful: %.3fGB/s memory: %.3fGB/s\n", useful, useful * traffic(test));
	for(int i = 0; i < threads; ++i) {
		std::free(src[i]);
		std::free(dst[i]);
	}
	return static_cast<int>(sink.load() == 42);
}
