// cpu_pack: the CPU side of copylib's staged copies, isolated (no GPU involved).
//
// A staged host -> device copy first packs the strided host side into a contiguous staging buffer ("pack"); device -> host unpacks
// contiguous data into the strided host layout ("unpack"). copylib does this per chunk in its workers with execute_copy's host path:
// for_each_copy_run + memcpy per contiguous run. Here the data is the column of strided_transfer: N rows of one 4-byte value, row
// pitch M * 4 bytes on the host.
//
// Variants:
//   copylib  copylib's own code: for_each_copy_run from <copylib/core.hpp> with memcpy, as in execute_copy (backend.cpp)
//   rowloop  plain row loop (pointer + stride, no index arithmetic per row), memcpy with the row width as a runtime length
//   fixed    the same row loop with the row width as a compile-time constant (1/2/4/8/16 bytes), so memcpy becomes one load/store
//   proposal copylib::detail::copy_host_to_host (host_copy.hpp), the general 3D replacement proposed for copylib
//
// Usage: cpu_pack <copylib|rowloop|fixed|proposal> <pack|unpack> <N> <M> <cpus> [chunk_bytes=16777216] [reps=3]
//   cpus: comma-separated CPU list, one worker per entry, worker i pinned to the i-th CPU (like COPYLIB_WORKER_CPUS)
// Output: "copy: <ns>ns, <GB/s>GB/s" (median of reps, GB/s on N * 4 bytes), "per row: <ns> ns", "Check: ok|FAILED"
#include <copylib/core.hpp>

#include "host_copy.hpp" // proposed replacement for copylib's host copy step

#include <algorithm>
#include <atomic>
#include <barrier>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>
#include <vector>

#include <pthread.h>
#include <sched.h>

using namespace copylib;

namespace {

enum class variant { copylib, rowloop, fixed, proposal };

// execute_copy's host <-> host path (gpu3dcopylib src/backend.cpp), unchanged
void copy_copylib(const copy_spec& spec) {
	const auto& source = spec.source_layout;
	const auto& target_layout = spec.target_layout;
	for_each_copy_run(spec, [&](int64_t source_offset, int64_t target_offset, int64_t length) {
		std::memcpy(target_layout.base_ptr() + target_offset, source.base_ptr() + source_offset, length);
	});
}

// One side of a copy as "rows of `width` bytes, `stride` bytes apart", starting at the window's first byte. Works for a contiguous
// 1D layout (stride = width) and for a 2D layout of one plane whose window starts and ends on row boundaries.
struct row_view {
	std::byte* first = nullptr;
	int64_t stride = 0;
	bool ok = false;
};

row_view view_rows(const data_layout& l, int64_t width) {
	const int64_t d0 = l.d0_end_offset - l.d0_start_offset;
	const int64_t d1 = l.d1_end_offset - l.d1_start_offset;
	const int64_t d2 = l.d2_end_offset - l.d2_start_offset;
	if(d1 == 1 && d2 == 1) return {l.base_ptr() + l.d0_start_offset + l.start, width, true}; // contiguous
	if(d2 == 1 && d0 == width && l.start % width == 0 && l.window_length() % width == 0) {
		return {l.base_ptr() + (l.d1_start_offset + l.start / width) * l.d0_stride + l.d0_start_offset, l.d0_stride, true};
	}
	return {};
}

template <int64_t W>
void copy_rows_fixed(std::byte* dst, int64_t dst_stride, const std::byte* src, int64_t src_stride, int64_t rows) {
	for(int64_t r = 0; r < rows; ++r) {
		std::memcpy(dst + r * dst_stride, src + r * src_stride, W);
	}
}

void copy_rows_runtime(std::byte* dst, int64_t dst_stride, const std::byte* src, int64_t src_stride, int64_t rows, int64_t width) {
	for(int64_t r = 0; r < rows; ++r) {
		std::memcpy(dst + r * dst_stride, src + r * src_stride, static_cast<size_t>(width));
	}
}

// returns false if the spec is not a row copy (then the caller falls back to copylib's path)
bool copy_rows(const copy_spec& spec, bool fixed_width) {
	const auto& s = spec.source_layout;
	const auto& t = spec.target_layout;
	const bool s_rows = !(s.d1_end_offset - s.d1_start_offset == 1 && s.d2_end_offset - s.d2_start_offset == 1);
	const int64_t width = s_rows ? s.d0_end_offset - s.d0_start_offset : t.d0_end_offset - t.d0_start_offset; // the strided side's row
	const row_view src = view_rows(s, width);
	const row_view dst = view_rows(t, width);
	if(!src.ok || !dst.ok || s.window_length() != t.window_length()) return false;
	const int64_t rows = s.window_length() / width;
	if(!fixed_width) {
		copy_rows_runtime(dst.first, dst.stride, src.first, src.stride, rows, width);
		return true;
	}
	switch(width) {
	case 1: copy_rows_fixed<1>(dst.first, dst.stride, src.first, src.stride, rows); return true;
	case 2: copy_rows_fixed<2>(dst.first, dst.stride, src.first, src.stride, rows); return true;
	case 4: copy_rows_fixed<4>(dst.first, dst.stride, src.first, src.stride, rows); return true;
	case 8: copy_rows_fixed<8>(dst.first, dst.stride, src.first, src.stride, rows); return true;
	case 16: copy_rows_fixed<16>(dst.first, dst.stride, src.first, src.stride, rows); return true;
	default: copy_rows_runtime(dst.first, dst.stride, src.first, src.stride, rows, width); return true;
	}
}

std::atomic<bool> g_fallback{false};

void run_copy(variant v, const copy_spec& spec) {
	if(v == variant::copylib) return copy_copylib(spec);
	if(v == variant::proposal) return detail::copy_host_to_host(spec);
	if(!copy_rows(spec, v == variant::fixed)) {
		g_fallback = true;
		copy_copylib(spec);
	}
}

uint32_t value(int64_t row) { return static_cast<uint32_t>(row) * 2654435761u ^ 0x5bd1e995u; }
constexpr uint32_t gap = 0xdeadbeefu;

void pin(int cpu) {
	cpu_set_t set;
	CPU_ZERO(&set);
	CPU_SET(cpu, &set);
	pthread_setaffinity_np(pthread_self(), sizeof(set), &set);
}

void* alloc(size_t bytes) {
	void* p = std::aligned_alloc(4096, (bytes + 4095) / 4096 * 4096);
	if(!p) {
		std::fprintf(stderr, "allocation of %zu bytes failed\n", bytes);
		std::exit(1);
	}
	return p;
}

} // namespace

int main(int argc, char** argv) {
	if(argc < 6) {
		std::fprintf(stderr, "usage: %s <copylib|rowloop|fixed|proposal> <pack|unpack> <N> <M> <cpus> [chunk_bytes] [reps]\n", argv[0]);
		return 1;
	}
	const std::string vname = argv[1];
	const variant v = vname == "copylib" ? variant::copylib : vname == "rowloop" ? variant::rowloop : vname == "proposal" ? variant::proposal : variant::fixed;
	const bool pack = std::string(argv[2]) == "pack";
	const int64_t N = std::stoll(argv[3]);
	const int64_t M = std::stoll(argv[4]);
	std::vector<int> cpus;
	for(const char* p = argv[5]; *p;) {
		cpus.push_back(std::atoi(p));
		while(*p && *p != ',') ++p;
		if(*p == ',') ++p;
	}
	const int64_t chunk = argc > 6 ? std::stoll(argv[6]) : 16 << 20;
	const int reps = argc > 7 ? std::atoi(argv[7]) : 3;
	const int workers = static_cast<int>(cpus.size());
	const int64_t total = N * 4; // packed bytes

	// host buffer: N rows of M values, value(row) in column 0, gap elsewhere; contiguous side: one staging slice per worker (pack) or
	// the whole packed data (unpack, standing in for the DMA-filled staging)
	auto* host = static_cast<uint32_t*>(alloc(static_cast<size_t>(N * M * 4)));
	for(int64_t r = 0; r < N; ++r) {
		host[r * M] = pack ? value(r) : 0;
		for(int64_t c = 1; c < M; ++c) host[r * M + c] = gap;
	}
	std::vector<uint32_t*> staging(workers);
	uint32_t* packed = nullptr;
	if(pack) {
		for(auto& s : staging) {
			s = static_cast<uint32_t*>(alloc(static_cast<size_t>(chunk)));
			std::memset(s, 0, static_cast<size_t>(chunk));
		}
	} else {
		packed = static_cast<uint32_t*>(alloc(static_cast<size_t>(total)));
		for(int64_t r = 0; r < N; ++r) packed[r] = value(r);
	}

	// the column as Celerity hands it to copylib after normalization: 2D, rows of 4 bytes with a pitch of M * 4 bytes
	const data_layout host_layout(reinterpret_cast<intptr_t>(host), M * 4, N, 0, 0, 0, 4, N, 1);
	const data_layout packed_layout = pack ? data_layout() : data_layout(reinterpret_cast<intptr_t>(packed), 0, total);
	const int64_t chunks = (total + chunk - 1) / chunk;

	std::atomic<bool> check_ok{true};
	auto work = [&](int w, bool verify) { // copylib's default plan order: worker w takes the w-th contiguous block of chunks
		const int64_t first = chunks * w / workers, last = chunks * (w + 1) / workers;
		for(int64_t c = first; c < last; ++c) {
			const int64_t s = c * chunk, e = std::min(total, s + chunk);
			if(pack) {
				const copy_spec spec(device_id::host, host_layout.with_window(s, e), device_id::host,
				    data_layout(reinterpret_cast<intptr_t>(staging[w]), 0, e - s));
				run_copy(v, spec);
				if(verify) {
					for(int64_t i = 0; i < (e - s) / 4; ++i) {
						if(staging[w][i] != value(s / 4 + i)) check_ok = false;
					}
				}
			} else {
				const copy_spec spec(device_id::host, packed_layout.with_window(s, e), device_id::host, host_layout.with_window(s, e));
				run_copy(v, spec);
			}
		}
	};

	// persistent workers like copylib's pool; worker 0 is the main thread
	std::barrier start(workers), done(workers);
	std::atomic<bool> quit{false}, verify_pass{false};
	std::vector<std::thread> threads;
	for(int w = 1; w < workers; ++w) {
		threads.emplace_back([&, w] {
			pin(cpus[w]);
			for(;;) {
				start.arrive_and_wait();
				if(quit) return;
				work(w, verify_pass);
				done.arrive_and_wait();
			}
		});
	}
	pin(cpus[0]);
	auto timed = [&](bool verify) {
		verify_pass = verify;
		start.arrive_and_wait();
		const auto t0 = std::chrono::steady_clock::now();
		work(0, verify);
		done.arrive_and_wait();
		return std::chrono::duration<double, std::nano>(std::chrono::steady_clock::now() - t0).count();
	};

	timed(false); // warmup: touches every page once
	std::vector<double> ns;
	for(int r = 0; r < reps; ++r) ns.push_back(timed(false));
	if(pack) timed(true); // untimed pass that checks every chunk
	quit = true;
	start.arrive_and_wait();
	for(auto& t : threads) t.join();

	if(!pack) {
		for(int64_t r = 0; r < N; ++r) {
			if(host[r * M] != value(r)) check_ok = false;
			for(int64_t c = 1; c < M; ++c) {
				if(host[r * M + c] != gap) check_ok = false;
			}
		}
	}
	std::sort(ns.begin(), ns.end());
	const double med = ns[ns.size() / 2];
	std::printf("Data Size: %.9f GiB\n", static_cast<double>(total) / (1 << 30));
	std::printf("variant %s, %s, N %lld, M %lld, workers %d, chunk %lld, fast path %s\n", vname.c_str(), pack ? "pack" : "unpack",
	    static_cast<long long>(N), static_cast<long long>(M), workers, static_cast<long long>(chunk),
	    (v == variant::copylib || v == variant::proposal) ? "-" : (g_fallback ? "fallback" : "yes"));
	std::printf("copy: %.0fns, %.6fGB/s\n", med, static_cast<double>(total) / med);
	std::printf("per row: %.3f ns\n", med * workers / static_cast<double>(N));
	std::printf("Check: %s\n", check_ok ? "ok" : "FAILED");
	return check_ok ? 0 : 2;
}
