#pragma once

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

// Shared protocol of all overhead_* programs. See README.md.
//   <program> <tasks> <elems> <buffers> [reps=7] [latency_samples=200]
// Every task increments each of `elems` ints of buffer (task_index % buffers) by one.
// buffers=1 forms a dependency chain, a large value gives (mostly) independent tasks.
namespace bench {

using clock_type = std::chrono::steady_clock;

inline double us_between(const clock_type::time_point a, const clock_type::time_point b) {
	return std::chrono::duration<double, std::micro>(b - a).count();
}

inline double median(std::vector<double> v) {
	std::sort(v.begin(), v.end());
	return v[v.size() / 2];
}

struct config {
	std::string impl;
	size_t tasks = 1000;
	size_t elems = 1024;
	size_t buffers = 1;
	size_t reps = 7;
	size_t latency_samples = 200;
	size_t warmup_tasks = 64;
	int strided = 0; // celerity only
};

inline config parse_args(const char* impl, const int argc, char** argv) {
	if(argc < 4) {
		std::fprintf(stderr, "Usage: %s <tasks> <elems> <buffers> [reps=7] [latency_samples=200]\n", argv[0]);
		std::exit(2);
	}
	config c;
	c.impl = impl;
	c.tasks = std::strtoull(argv[1], nullptr, 10);
	c.elems = std::strtoull(argv[2], nullptr, 10);
	c.buffers = std::strtoull(argv[3], nullptr, 10);
	if(argc > 4) c.reps = std::strtoull(argv[4], nullptr, 10);
	if(argc > 5) c.latency_samples = std::strtoull(argv[5], nullptr, 10);
	if(c.tasks == 0 || c.elems == 0 || c.buffers == 0 || c.reps == 0 || c.latency_samples == 0) {
		std::fprintf(stderr, "all arguments must be positive\n");
		std::exit(2);
	}
	return c;
}

/// Mirrors on the host how often every buffer was incremented, for the final correctness check.
class tally {
  public:
	explicit tally(const size_t buffers) : m_buffers(buffers), m_counts(buffers, 0) {}
	size_t buffer_for_task(const size_t task_index) const { return task_index % m_buffers; }
	void on_task(const size_t task_index) { ++m_counts[buffer_for_task(task_index)]; }
	int expected(const size_t buffer) const { return m_counts[buffer]; }
	size_t buffers() const { return m_buffers; }

  private:
	size_t m_buffers;
	std::vector<int> m_counts;
};

/// `submit_one(i)` enqueues task number i (non-blocking), `wait_all()` blocks until everything enqueued has completed.
/// Calls the callbacks in this order: warmup, `reps` x (N submissions, wait), `latency_samples` x (1 submission, wait).
template <typename SubmitOne, typename WaitAll>
void run_protocol(const config& c, tally& t, SubmitOne&& submit_one, WaitAll&& wait_all) {
	size_t next = 0;
	const auto submit = [&] {
		const auto i = next++;
		t.on_task(i);
		submit_one(i);
	};

	for(size_t i = 0; i < c.warmup_tasks; ++i) submit();
	wait_all();

	std::vector<double> submit_us, total_us, drain_us, latency_us;
	for(size_t r = 0; r < c.reps; ++r) {
		const auto t0 = clock_type::now();
		for(size_t i = 0; i < c.tasks; ++i) submit();
		const auto t1 = clock_type::now();
		wait_all();
		const auto t2 = clock_type::now();
		submit_us.push_back(us_between(t0, t1) / static_cast<double>(c.tasks));
		total_us.push_back(us_between(t0, t2) / static_cast<double>(c.tasks));
		drain_us.push_back(us_between(t1, t2));
	}
	for(size_t s = 0; s < c.latency_samples; ++s) {
		const auto t0 = clock_type::now();
		submit();
		wait_all();
		latency_us.push_back(us_between(t0, clock_type::now()));
	}

	std::printf("Config: impl=%s tasks=%zu elems=%zu buffers=%zu reps=%zu strided=%d\n", c.impl.c_str(), c.tasks, c.elems, c.buffers, c.reps, c.strided);
	std::printf("Submit: %.3f us/task\n", median(submit_us));
	std::printf("Total: %.3f us/task\n", median(total_us));
	std::printf("Drain: %.1f us\n", median(drain_us));
	std::printf("Latency: %.2f us\n", median(latency_us));
}

inline void report_check(const bool ok) {
	std::printf("Check: %s\n", ok ? "ok" : "FAILED");
	std::fflush(stdout);
}

} // namespace bench
