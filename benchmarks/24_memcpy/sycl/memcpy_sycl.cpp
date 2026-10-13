// Plain SYCL (USM, in-order queue): sycl::malloc_device + queue::memcpy + queue::wait. Same source for AdaptiveCpp and DPC++.
// Host memory: sycl::malloc_host (pinned) or page-aligned pageable memory.
#include "memcpy_common.h"

#include <sycl/sycl.hpp>

#ifndef BENCH_IMPL
#define BENCH_IMPL "sycl"
#endif

int main(int argc, char** argv) {
	const auto c = bench::parse_args(BENCH_IMPL, argc, argv);

	sycl::queue q{sycl::gpu_selector_v, sycl::property::queue::in_order{}};
	unsigned char *src, *dst;
	if(c.pinned) {
		src = sycl::malloc_host<unsigned char>(c.bytes, q);
		dst = sycl::malloc_host<unsigned char>(c.bytes, q);
	} else {
		src = bench::alloc_pageable(c.bytes);
		dst = bench::alloc_pageable(c.bytes);
	}
	auto* dev = sycl::malloc_device<unsigned char>(c.bytes, q);
	bench::fill_pattern(src, c.bytes);
	std::memset(dst, 0, c.bytes);

	const auto wait = [&] { q.wait(); };
	const auto h2d = bench::measure(c.reps, [&] { q.memcpy(dev, src, c.bytes); }, wait);
	const auto d2h = bench::measure(c.reps, [&] { q.memcpy(dst, dev, c.bytes); }, wait);

	bench::print_config(c, c.pinned ? "pinned" : "pageable");
	bench::print_result("H2D", c.bytes, h2d);
	bench::print_result("D2H", c.bytes, d2h);
	bench::report_check(bench::check_pattern(dst, c.bytes));
	return 0;
}
