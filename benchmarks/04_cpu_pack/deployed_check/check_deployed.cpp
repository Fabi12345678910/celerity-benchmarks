// Runs host_copy_tests.cpp's 200k random cases against BOTH the proposed ../host_copy.hpp and the deployed copy_host_to_host of
// gpu3dcopylib src/backend.cpp (extracted by build.sh into deployed_body.inc; 014e21a incl. NT stores), each compared with
// for_each_copy_run + memcpy, i.e. every target byte incl. the untouched ones. Usage: ./check_deployed [cases=200000]
#include <copylib/core.hpp>
#include <copylib/host_copy.hpp>
#include <immintrin.h>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <random>
#include <vector>
using namespace copylib;
namespace deployed {
#include "deployed_body.inc"
}
namespace {
std::mt19937_64 rng(12345);
int64_t rnd(int64_t lo, int64_t hi) { return std::uniform_int_distribution<int64_t>(lo, hi)(rng); }
struct allocation { int64_t row, rows, planes; };
data_layout random_box(intptr_t base, allocation a, int64_t width = 0) {
	const int64_t w = width != 0 ? width : rnd(1, a.row);
	const int64_t d0s = rnd(0, a.row - w), d1s = rnd(0, a.rows - 1), d1e = rnd(d1s + 1, a.rows), d2s = rnd(0, a.planes - 1);
	const int64_t d2e = rnd(d2s + 1, a.planes);
	return data_layout(base, a.row, a.rows, d0s, d1s, d2s, d0s + w, d1e, d2e);
}
}
int main(int argc, char** argv) {
	const long iters = argc > 1 ? atol(argv[1]) : 200000;
	long fail_prop = 0, fail_dep = 0, staged = 0;
	const int64_t widths[] = {1, 2, 3, 4, 5, 8, 12, 16, 24, 32, 40, 64, 100};
	for(long iter = 0; iter < iters; ++iter) {
		const int kind = iter % 3;
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
		std::vector<std::byte> prop = expected, dep = expected;
		for_each_copy_run(copy_spec(device_id::host, sl, device_id::host, tl),
		    [&](int64_t so, int64_t to, int64_t n) { std::memcpy(expected.data() + to, sl.base_ptr() + so, n); });
		detail::copy_host_to_host(copy_spec(device_id::host, sl, device_id::host, data_layout(reinterpret_cast<intptr_t>(prop.data()), tl)));
		deployed::copy_host_to_host(copy_spec(device_id::host, sl, device_id::host, data_layout(reinterpret_cast<intptr_t>(dep.data()), tl)));
		if(kind != 0) ++staged;
		if(prop != expected) ++fail_prop;
		if(dep != expected) { if(++fail_dep <= 3) std::printf("deployed mismatch at iter %ld (kind %d, w %ld)\n", iter, kind, (long)w); }
	}
	std::printf("cases %ld (staging shapes %ld): proposed failures %ld, deployed failures %ld\n", iters, staged, fail_prop, fail_dep);
	return (fail_prop || fail_dep) ? 1 : 0;
}
