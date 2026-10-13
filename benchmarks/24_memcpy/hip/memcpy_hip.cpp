// Direct HIP: one stream, hipMalloc'd device memory, hipMemcpyAsync + hipStreamSynchronize.
// Host memory: hipHostMalloc (default flags, as acpp and DPC++ allocate pinned memory) or page-aligned pageable memory.
#include "memcpy_common.h"

#include <hip/hip_runtime.h>

#define HIP_CHECK(expr)                                                                                                                                        \
	do {                                                                                                                                                       \
		const hipError_t err_ = (expr);                                                                                                                        \
		if(err_ != hipSuccess) {                                                                                                                               \
			std::fprintf(stderr, "%s:%d: %s failed: %s\n", __FILE__, __LINE__, #expr, hipGetErrorString(err_));                                                \
			std::exit(1);                                                                                                                                      \
		}                                                                                                                                                      \
	} while(0)

int main(int argc, char** argv) {
	const auto c = bench::parse_args("hip", argc, argv);

	HIP_CHECK(hipSetDevice(0));
	hipStream_t stream;
	HIP_CHECK(hipStreamCreate(&stream));

	unsigned char *src, *dst, *dev;
	if(c.pinned) {
		HIP_CHECK(hipHostMalloc(reinterpret_cast<void**>(&src), c.bytes));
		HIP_CHECK(hipHostMalloc(reinterpret_cast<void**>(&dst), c.bytes));
	} else {
		src = bench::alloc_pageable(c.bytes);
		dst = bench::alloc_pageable(c.bytes);
	}
	HIP_CHECK(hipMalloc(reinterpret_cast<void**>(&dev), c.bytes));
	bench::fill_pattern(src, c.bytes);
	std::memset(dst, 0, c.bytes);

	const auto wait = [&] { HIP_CHECK(hipStreamSynchronize(stream)); };
	const auto h2d = bench::measure(c.reps, [&] { HIP_CHECK(hipMemcpyAsync(dev, src, c.bytes, hipMemcpyHostToDevice, stream)); }, wait);
	const auto d2h = bench::measure(c.reps, [&] { HIP_CHECK(hipMemcpyAsync(dst, dev, c.bytes, hipMemcpyDeviceToHost, stream)); }, wait);

	bench::print_config(c, c.pinned ? "pinned" : "pageable");
	bench::print_result("H2D", c.bytes, h2d);
	bench::print_result("D2H", c.bytes, d2h);
	bench::report_check(bench::check_pattern(dst, c.bytes));
	return 0;
}
