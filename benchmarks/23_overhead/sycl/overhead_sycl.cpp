// Plain SYCL (USM, in-order queue). Same source for AdaptiveCpp and DPC++.
#include "bench_common.h"

#include <sycl/sycl.hpp>

#include <vector>

#ifndef BENCH_IMPL
#define BENCH_IMPL "sycl"
#endif

class increment_kernel;

int main(int argc, char** argv) {
	const auto c = bench::parse_args(BENCH_IMPL, argc, argv);

	sycl::queue q{sycl::gpu_selector_v, sycl::property::queue::in_order{}};
	std::vector<int*> bufs(c.buffers);
	for(auto& b : bufs) {
		b = sycl::malloc_device<int>(c.elems, q);
		q.fill(b, 0, c.elems);
	}
	q.wait();

	bench::tally tally(c.buffers);
	const auto n = c.elems;
	bench::run_protocol(
	    c, tally,
	    [&](const size_t i) {
		    int* const p = bufs[tally.buffer_for_task(i)];
		    q.parallel_for<increment_kernel>(sycl::range<1>(n), [=](sycl::id<1> id) { p[id] += 1; });
	    },
	    [&] { q.wait_and_throw(); });

	bool ok = true;
	std::vector<int> host(c.elems);
	for(size_t b = 0; b < c.buffers; ++b) {
		q.memcpy(host.data(), bufs[b], c.elems * sizeof(int)).wait();
		for(const int v : host) ok &= v == tally.expected(b);
	}
	for(auto* b : bufs) sycl::free(b, q);
	bench::report_check(ok);
	return ok ? 0 : 1;
}
