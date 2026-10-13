// Celerity (one process, one device). Celerity has no explicit copy call: copies follow from accessors. A host->device copy is forced by
// a host task writing the whole buffer (no_init, no work) followed by a one-item kernel reading it; device->host by a kernel writing it
// followed by a host task reading it. Host memory is Celerity's own (pinned) allocation, so there is no host argument.
// Printed per direction: "<dir> tasks" = the forcing task pair, "<dir> base" = the same pair where the copy is not needed (the host
// task touches a 1-byte dummy buffer instead), "<dir>" = tasks minus base (the copy as Celerity issues it, incl. its bookkeeping).
// Contiguous copies are never routed to copylib, so copylib settings do not apply.
#include "memcpy_common.h"

#include <celerity.h>

#ifndef BENCH_IMPL
#define BENCH_IMPL "celerity"
#endif

int main(int argc, char** argv) {
	const auto c = bench::parse_args(BENCH_IMPL, argc, argv, false);
	const size_t n = c.bytes;

	celerity::queue q;
	celerity::buffer<unsigned char, 1> buf{celerity::range<1>(n)};
	celerity::buffer<unsigned char, 1> dummy{celerity::range<1>(1)};

	const auto host_write = [&](celerity::buffer<unsigned char, 1>& b) {
		q.submit([&](celerity::handler& cgh) {
			celerity::accessor acc(b, cgh, celerity::access::all(), celerity::write_only_host_task, celerity::no_init);
			cgh.host_task(celerity::on_master_node, [=] { (void)acc; });
		});
	};
	const auto host_read = [&](celerity::buffer<unsigned char, 1>& b) {
		q.submit([&](celerity::handler& cgh) {
			celerity::accessor acc(b, cgh, celerity::access::all(), celerity::read_only_host_task);
			cgh.host_task(celerity::on_master_node, [=] { (void)acc; });
		});
	};
	const auto device_read = [&] {
		q.submit([&](celerity::handler& cgh) {
			celerity::accessor acc(buf, cgh, celerity::access::all(), celerity::read_only);
			cgh.parallel_for<class read_kernel>(celerity::range<1>(1), [=](celerity::item<1>) { (void)acc; });
		});
	};
	const auto device_write = [&] {
		q.submit([&](celerity::handler& cgh) {
			celerity::accessor acc(buf, cgh, celerity::access::all(), celerity::write_only, celerity::no_init);
			cgh.parallel_for<class write_kernel>(celerity::range<1>(1), [=](celerity::item<1>) { (void)acc; });
		});
	};
	host_write(dummy);
	const auto wait = [&] { q.wait(); };

	const auto h2d = bench::measure(c.reps, [&] { host_write(buf); device_read(); }, wait);
	const auto h2d_base = bench::measure(c.reps, [&] { host_write(dummy); device_read(); }, wait);
	const auto d2h = bench::measure(c.reps, [&] { device_write(); host_read(buf); }, wait);
	const auto d2h_base = bench::measure(c.reps, [&] { device_write(); host_read(dummy); }, wait);
	const auto net = [](const bench::result& a, const bench::result& b) {
		return bench::result{a.median_us - b.median_us, a.min_us - b.min_us, a.stream_us - b.stream_us, a.submit_us - b.submit_us};
	};

	// correctness: host writes the pattern, the device adds 1 (H2D), the host reads it back (D2H)
	q.submit([&](celerity::handler& cgh) {
		celerity::accessor acc(buf, cgh, celerity::access::all(), celerity::write_only_host_task, celerity::no_init);
		cgh.host_task(celerity::on_master_node, [=] {
			for(size_t i = 0; i < n; ++i) acc[celerity::id<1>(i)] = bench::pattern(i);
		});
	});
	q.submit([&](celerity::handler& cgh) {
		celerity::accessor acc(buf, cgh, celerity::access::one_to_one(), celerity::read_write);
		cgh.parallel_for<class check_kernel>(celerity::range<1>(n), [=](celerity::item<1> item) { acc[item] += 1; });
	});
	const auto snapshot = q.fence(buf, celerity::subrange<1>(0, n)).get();

	bench::print_config(c, "celerity");
	bench::print_result("H2D", n, net(h2d, h2d_base));
	bench::print_result("D2H", n, net(d2h, d2h_base));
	bench::print_result("H2D tasks", n, h2d);
	bench::print_result("H2D base", n, h2d_base);
	bench::print_result("D2H tasks", n, d2h);
	bench::print_result("D2H base", n, d2h_base);
	bench::report_check(bench::check_pattern(snapshot.get_data(), n, 1));
	return 0;
}
