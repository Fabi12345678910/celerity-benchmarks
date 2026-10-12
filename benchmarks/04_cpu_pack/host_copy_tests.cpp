#include <copylib/core.hpp>
#include <copylib/host_copy.hpp>

#include <catch2/catch_test_macros.hpp>

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <random>
#include <vector>

// copy_host_to_host must write exactly the bytes that for_each_copy_run + memcpy (the previous host copy step) writes: random 3D
// boxes with gaps in every dimension, windows starting and ending mid-row, different row widths on both sides, and the staging shapes
// (strided <-> contiguous) with every specialized row width.

using namespace copylib;

namespace {

std::mt19937_64 rng(12345);
int64_t rnd(int64_t lo, int64_t hi) { return std::uniform_int_distribution<int64_t>(lo, hi)(rng); }

struct allocation {
	int64_t row, rows, planes;
};

data_layout random_box(intptr_t base, allocation a, int64_t width = 0) {
	const int64_t w = width != 0 ? width : rnd(1, a.row);
	const int64_t d0s = rnd(0, a.row - w), d1s = rnd(0, a.rows - 1), d1e = rnd(d1s + 1, a.rows), d2s = rnd(0, a.planes - 1);
	const int64_t d2e = rnd(d2s + 1, a.planes);
	return data_layout(base, a.row, a.rows, d0s, d1s, d2s, d0s + w, d1e, d2e);
}

} // namespace

TEST_CASE("copy_host_to_host matches for_each_copy_run with memcpy", "[host_copy]") {
	const int64_t widths[] = {1, 2, 3, 4, 5, 8, 12, 16, 24, 32, 40, 64, 100};
	for(int iter = 0; iter < 200000; ++iter) {
		const int kind = iter % 3; // 0: two random 3D boxes, 1: strided -> contiguous (pack), 2: contiguous -> strided (unpack)
		const int64_t w = widths[rnd(0, std::size(widths) - 1)];
		const allocation sa{rnd(w, w * 4 + 8), rnd(1, 9), rnd(1, 4)}, ta{rnd(w, w * 4 + 8), rnd(1, 9), rnd(1, 4)};
		std::vector<std::byte> src(sa.row * sa.rows * sa.planes), expected(ta.row * ta.rows * ta.planes);
		data_layout sl, tl;
		if(kind == 0) {
			sl = random_box(reinterpret_cast<intptr_t>(src.data()), sa);
			tl = random_box(reinterpret_cast<intptr_t>(expected.data()), ta);
		} else {
			const data_layout strided = random_box(0, kind == 1 ? sa : ta, w);
			const int64_t total = strided.total_bytes();
			if(kind == 1) {
				sl = data_layout(reinterpret_cast<intptr_t>(src.data()), strided);
				expected.resize(total + 16);
				tl = data_layout(reinterpret_cast<intptr_t>(expected.data()), rnd(0, 16), total);
			} else {
				src.resize(total + 16);
				sl = data_layout(reinterpret_cast<intptr_t>(src.data()), rnd(0, 16), total);
				tl = data_layout(reinterpret_cast<intptr_t>(expected.data()), strided);
			}
		}
		for(auto& b : src) b = std::byte(rnd(0, 255));
		const int64_t length = rnd(0, std::min(sl.total_bytes(), tl.total_bytes()));
		const int64_t s = rnd(0, sl.total_bytes() - length), t = rnd(0, tl.total_bytes() - length);
		sl = sl.with_window(s, s + length);
		tl = tl.with_window(t, t + length);
		std::fill(expected.begin(), expected.end(), std::byte(0xab));
		std::vector<std::byte> actual = expected;

		const copy_spec reference(device_id::host, sl, device_id::host, tl);
		for_each_copy_run(reference, [&](int64_t so, int64_t to, int64_t n) { std::memcpy(expected.data() + to, sl.base_ptr() + so, n); });
		detail::copy_host_to_host(copy_spec(device_id::host, sl, device_id::host, data_layout(reinterpret_cast<intptr_t>(actual.data()), tl)));

		REQUIRE(actual == expected);
	}
}
