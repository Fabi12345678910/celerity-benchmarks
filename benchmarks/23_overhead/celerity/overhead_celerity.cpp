// Celerity. The same source is linked against a copylib and a no-copylib installation of Celerity (see build.sh).
// Optional 6th argument `strided=1`: buffers become 2D (elems rows x 16 columns) and every kernel is followed by a
// host task reading column 0, which forces a strided device-to-host copy per task (routed to copylib in copylib builds).
// In that mode a task is a kernel plus a host task, and the kernel covers elems x 16 items.
#include "bench_common.h"

#include <celerity.h>

#include <vector>

#ifndef BENCH_IMPL
#define BENCH_IMPL "celerity"
#endif

constexpr size_t strided_cols = 16;

class increment_kernel_1d;
class increment_kernel_2d;

int main(int argc, char** argv) {
	auto c = bench::parse_args(BENCH_IMPL, argc, argv);
	if(argc > 6) c.strided = std::atoi(argv[6]);

	celerity::queue q;
	const bool strided = c.strided != 0;
	const size_t elems = c.elems;

	std::vector<celerity::buffer<int, 1>> bufs1;
	std::vector<celerity::buffer<int, 2>> bufs2;
	for(size_t b = 0; b < c.buffers; ++b) {
		if(strided) {
			bufs2.emplace_back(celerity::range<2>(elems, strided_cols));
		} else {
			bufs1.emplace_back(celerity::range<1>(elems));
		}
	}
	// zero-initialize on the device
	for(size_t b = 0; b < c.buffers; ++b) {
		if(strided) {
			q.submit([&](celerity::handler& cgh) {
				celerity::accessor acc(bufs2[b], cgh, celerity::access::one_to_one(), celerity::write_only, celerity::no_init);
				cgh.parallel_for<class zero_kernel_2d>(celerity::range<2>(elems, strided_cols), [=](celerity::item<2> item) { acc[item] = 0; });
			});
		} else {
			q.submit([&](celerity::handler& cgh) {
				celerity::accessor acc(bufs1[b], cgh, celerity::access::one_to_one(), celerity::write_only, celerity::no_init);
				cgh.parallel_for<class zero_kernel_1d>(celerity::range<1>(elems), [=](celerity::item<1> item) { acc[item] = 0; });
			});
		}
	}
	q.wait();

	bench::tally tally(c.buffers);
	bench::run_protocol(
	    c, tally,
	    [&](const size_t i) {
		    const auto b = tally.buffer_for_task(i);
		    if(strided) {
			    q.submit([&](celerity::handler& cgh) {
				    celerity::accessor acc(bufs2[b], cgh, celerity::access::one_to_one(), celerity::read_write);
				    cgh.parallel_for<increment_kernel_2d>(celerity::range<2>(elems, strided_cols), [=](celerity::item<2> item) { acc[item] += 1; });
			    });
			    q.submit([&](celerity::handler& cgh) {
				    celerity::accessor acc(bufs2[b], cgh, celerity::access::fixed<2>(celerity::subrange<2>({0, 0}, {elems, 1})), celerity::read_only_host_task);
				    cgh.host_task(celerity::on_master_node, [=] { (void)acc; });
			    });
		    } else {
			    q.submit([&](celerity::handler& cgh) {
				    celerity::accessor acc(bufs1[b], cgh, celerity::access::one_to_one(), celerity::read_write);
				    cgh.parallel_for<increment_kernel_1d>(celerity::range<1>(elems), [=](celerity::item<1> item) { acc[item] += 1; });
			    });
		    }
	    },
	    [&] { q.wait(); });

	bool ok = true;
	for(size_t b = 0; b < c.buffers; ++b) {
		if(strided) {
			const auto snapshot = q.fence(bufs2[b], celerity::subrange<2>({0, 0}, {elems, strided_cols})).get();
			const int* data = snapshot.get_data();
			for(size_t k = 0; k < elems * strided_cols; ++k) ok &= data[k] == tally.expected(b);
		} else {
			const auto snapshot = q.fence(bufs1[b], celerity::subrange<1>(0, elems)).get();
			const int* data = snapshot.get_data();
			for(size_t k = 0; k < elems; ++k) ok &= data[k] == tally.expected(b);
		}
	}
	bench::report_check(ok);
	return ok ? 0 : 1;
}
