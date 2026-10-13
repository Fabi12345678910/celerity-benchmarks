// first_copy: one contiguous copy between pinned host memory (hipHostMalloc) and device memory, timed the way the Celerity programs time
// "first access": std::chrono::steady_clock around the copy plus a synchronisation, on the FIRST copy after allocation (no warm-up), then
// the same for 5 further copies, plus HIP event times (as 07_limits/linkbw does). Answers whether the Celerity block numbers above the
// linkbw DMA rate come from the timing method. Usage: first_copy <h2d|d2h> <MiB>   Output: one line per copy, GB/s of the copied bytes.
#include <hip/hip_runtime.h>

#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#define CHECK(x) do { hipError_t e = (x); if(e != hipSuccess) { std::fprintf(stderr, "%s: %s\n", #x, hipGetErrorString(e)); std::exit(1); } } while(0)

int main(int argc, char** argv) {
	if(argc < 3) { std::fprintf(stderr, "usage: %s <h2d|d2h> <MiB>\n", argv[0]); return 1; }
	const bool h2d = std::string(argv[1]) == "h2d";
	const size_t bytes = static_cast<size_t>(std::atoll(argv[2])) << 20;
	void *host, *dev;
	CHECK(hipHostMalloc(&host, bytes, hipHostMallocDefault));
	CHECK(hipMalloc(&dev, bytes));
	std::memset(host, 1, bytes);
	CHECK(hipMemset(dev, 2, bytes));
	CHECK(hipDeviceSynchronize());
	hipEvent_t a, b;
	CHECK(hipEventCreate(&a));
	CHECK(hipEventCreate(&b));
	for(int r = 0; r < 6; ++r) {
		const auto t0 = std::chrono::steady_clock::now();
		CHECK(hipEventRecord(a, nullptr));
		if(h2d) CHECK(hipMemcpyAsync(dev, host, bytes, hipMemcpyHostToDevice, nullptr));
		else CHECK(hipMemcpyAsync(host, dev, bytes, hipMemcpyDeviceToHost, nullptr));
		CHECK(hipEventRecord(b, nullptr));
		CHECK(hipEventSynchronize(b));
		const double wall = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
		float ms = 0;
		CHECK(hipEventElapsedTime(&ms, a, b));
		std::printf("%s copy %d: wall %.3f GB/s  event %.3f GB/s\n", argv[1], r, bytes / wall / 1e9, bytes / (ms / 1e3) / 1e9);
	}
	return 0;
}
