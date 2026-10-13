// Direct HIP: one stream, hipMalloc'd buffers, hipLaunchKernelGGL.
#include "bench_common.h"

#include <hip/hip_runtime.h>

#include <vector>

#define HIP_CHECK(expr)                                                                                                                                        \
	do {                                                                                                                                                       \
		const hipError_t err_ = (expr);                                                                                                                        \
		if(err_ != hipSuccess) {                                                                                                                               \
			std::fprintf(stderr, "%s:%d: %s failed: %s\n", __FILE__, __LINE__, #expr, hipGetErrorString(err_));                                                \
			std::exit(1);                                                                                                                                      \
		}                                                                                                                                                      \
	} while(0)

__global__ void increment_kernel(int* p, const size_t n) {
	const size_t i = static_cast<size_t>(blockIdx.x) * blockDim.x + threadIdx.x;
	if(i < n) p[i] += 1;
}

int main(int argc, char** argv) {
	const auto c = bench::parse_args("hip", argc, argv);

	HIP_CHECK(hipSetDevice(0));
	hipStream_t stream;
	HIP_CHECK(hipStreamCreate(&stream));

	std::vector<int*> bufs(c.buffers);
	for(auto& b : bufs) {
		HIP_CHECK(hipMalloc(&b, c.elems * sizeof(int)));
		HIP_CHECK(hipMemsetAsync(b, 0, c.elems * sizeof(int), stream));
	}
	HIP_CHECK(hipStreamSynchronize(stream));

	constexpr unsigned block = 256;
	const unsigned grid = static_cast<unsigned>((c.elems + block - 1) / block);

	bench::tally tally(c.buffers);
	bench::run_protocol(
	    c, tally,
	    [&](const size_t i) {
		    hipLaunchKernelGGL(increment_kernel, dim3(grid), dim3(block), 0, stream, bufs[tally.buffer_for_task(i)], c.elems);
	    },
	    [&] {
		    HIP_CHECK(hipGetLastError());
		    HIP_CHECK(hipStreamSynchronize(stream));
	    });

	bool ok = true;
	std::vector<int> host(c.elems);
	for(size_t b = 0; b < c.buffers; ++b) {
		HIP_CHECK(hipMemcpy(host.data(), bufs[b], c.elems * sizeof(int), hipMemcpyDeviceToHost));
		for(const int v : host) ok &= v == tally.expected(b);
	}
	for(auto* b : bufs) HIP_CHECK(hipFree(b));
	HIP_CHECK(hipStreamDestroy(stream));
	bench::report_check(ok);
	return ok ? 0 : 1;
}
