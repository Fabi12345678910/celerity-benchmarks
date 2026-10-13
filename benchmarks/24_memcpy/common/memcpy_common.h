#pragma once

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

// Shared protocol of all memcpy_* programs: one contiguous copy of <bytes> host->device (H2D) and device->host (D2H).
//   <program> <bytes> [reps=30] [host=pinned|pageable]
// Per direction: 3 warmup copies, then `reps` single copies (copy + wait, timed one by one: median and minimum),
// then `reps` copies issued back to back with one wait at the end (Stream: time per copy, Submit: issue time per copy).
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
	size_t bytes = 0;
	size_t reps = 30;
	bool pinned = true;
};

inline config parse_args(const char* impl, const int argc, char** argv, const bool has_host_arg = true) {
	if(argc < 2) {
		std::fprintf(stderr, "Usage: %s <bytes> [reps=30]%s\n", argv[0], has_host_arg ? " [host=pinned|pageable]" : "");
		std::exit(2);
	}
	config c;
	c.impl = impl;
	c.bytes = std::strtoull(argv[1], nullptr, 10);
	if(argc > 2) c.reps = std::strtoull(argv[2], nullptr, 10);
	if(argc > 3 && has_host_arg) {
		const std::string h = argv[3];
		if(h != "pinned" && h != "pageable") {
			std::fprintf(stderr, "host must be pinned or pageable\n");
			std::exit(2);
		}
		c.pinned = h == "pinned";
	}
	if(c.bytes == 0 || c.reps == 0) {
		std::fprintf(stderr, "bytes and reps must be positive\n");
		std::exit(2);
	}
	return c;
}

inline void print_config(const config& c, const char* host) {
	std::printf("Config: impl=%s bytes=%zu reps=%zu host=%s\n", c.impl.c_str(), c.bytes, c.reps, host);
}

struct result {
	double median_us, min_us, stream_us, submit_us;
};

/// `copy()` issues one copy (may return before it completed), `wait()` blocks until all issued copies completed.
template <typename Copy, typename Wait>
result measure(const size_t reps, Copy&& copy, Wait&& wait) {
	for(int i = 0; i < 3; ++i) {
		copy();
		wait();
	}
	std::vector<double> single;
	for(size_t r = 0; r < reps; ++r) {
		const auto t0 = clock_type::now();
		copy();
		wait();
		single.push_back(us_between(t0, clock_type::now()));
	}
	const auto t0 = clock_type::now();
	for(size_t r = 0; r < reps; ++r) copy();
	const auto t1 = clock_type::now();
	wait();
	const auto t2 = clock_type::now();
	return {median(single), *std::min_element(single.begin(), single.end()), us_between(t0, t2) / reps, us_between(t0, t1) / reps};
}

/// One line per direction, e.g. "H2D: 12.34 us median, 11.80 us min, 5.312 GB/s, stream 10.10 us/copy, submit 1.20 us/copy".
/// GB/s = bytes / median time (bytes per ns).
inline void print_result(const char* dir, const size_t bytes, const result& r) {
	std::printf("%s: %.2f us median, %.2f us min, %.3f GB/s, stream %.2f us/copy, submit %.2f us/copy\n", dir, r.median_us, r.min_us,
	    static_cast<double>(bytes) / (r.median_us * 1e3), r.stream_us, r.submit_us);
}

inline unsigned char pattern(const size_t i) { return static_cast<unsigned char>(i * 7 + 3); }

inline void fill_pattern(unsigned char* p, const size_t n) {
	for(size_t i = 0; i < n; ++i) p[i] = pattern(i);
}

inline bool check_pattern(const unsigned char* p, const size_t n, const int offset = 0) {
	for(size_t i = 0; i < n; ++i)
		if(p[i] != static_cast<unsigned char>(pattern(i) + offset)) return false;
	return true;
}

/// Page-aligned pageable host memory (std::aligned_alloc needs a multiple of the alignment).
inline unsigned char* alloc_pageable(const size_t bytes) {
	return static_cast<unsigned char*>(std::aligned_alloc(4096, (bytes + 4095) / 4096 * 4096));
}

inline void report_check(const bool ok) {
	std::printf("Check: %s\n", ok ? "ok" : "FAILED");
	std::fflush(stdout);
}

} // namespace bench
