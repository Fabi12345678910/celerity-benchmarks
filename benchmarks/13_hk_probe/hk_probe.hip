// hk_probe: why is copylib's host kernel slow on gpuc4 (PCIe)? A GPU kernel copies `rows` rows of S bytes between contiguous device
// memory and pinned host memory where the rows lie P bytes apart (the access pattern of COPYLIB_HOST_KERNEL=1), without Celerity or copylib.
//
// Usage: hk_probe <r|w> <S> <P> <E> <rows> [alloc=default] [order=natural] [reps=3] [wg=256] [items=1] [store=plain|nt]
//   r|w      r: host -> device (kernel reads host rows), w: device -> host (kernel writes host rows)
//   S, P     row width and pitch in bytes (S <= P; multiples of E)
//   E        bytes per access: 1, 2, 4, 8 or 16 (copylib: min(alignment, COPYLIB_MAX_ELEM_SIZE))
//   alloc    default (hipHostMallocDefault), coherent, noncoherent, wc (write-combined), register (aligned_alloc + hipHostRegister)
//   order    natural  thread i takes element i (consecutive threads -> consecutive rows, as copylib)
//            spread   consecutive threads take rows in different 64-byte lines; the rows sharing a line are far apart in time
//            d<D>     the rows sharing a 64-byte line are D elements apart (d1 = natural, spread = d<rows / rows per line>)
//            phase    w only: one launch per row slot of a 64-byte line (64 / P launches), each writing one row per line
//            filter   w only: the proposed copylib change, (62 + S) / P + 1 launches over the whole grid when S < P < 64, each
//                     writing only the rows r with r % launches == launch
//            rmw      w only: one thread per 16 host bytes reads them, merges the row bytes and writes all 16 back (whole lines, no
//                     partial writes; NOT safe if anyone else writes the gaps concurrently)
//   wg       work-group size; items: elements per thread (grid-stride over the elements, as COPYLIB_ELEMS_PER_ITEM)
//   store    w only: plain stores, or nt = __builtin_nontemporal_store (streaming, not kept in the GPU caches)
// Output: "probe: <GB/s>GB/s rows/s=<M> check=ok|FAILED" (median of reps after one warmup; GB/s on rows * S useful bytes, HIP events).
// Check: every row byte copied, every gap byte unchanged.
#include <hip/hip_runtime.h>

#include <algorithm>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#define CHECK(x)                                                                                                                      \
	do {                                                                                                                              \
		hipError_t e = (x);                                                                                                           \
		if(e != hipSuccess) {                                                                                                         \
			std::fprintf(stderr, "%s failed: %s\n", #x, hipGetErrorString(e));                                                       \
			std::exit(1);                                                                                                             \
		}                                                                                                                             \
	} while(0)

template <int E> struct elem_t;
template <> struct elem_t<1> { using type = uint8_t; };
template <> struct elem_t<2> { using type = uint16_t; };
template <> struct elem_t<4> { using type = uint32_t; };
template <> struct elem_t<8> { using type = uint2; };
template <> struct elem_t<16> { using type = uint4; };

// element e of the copy -> its row. The rows sharing a 64-byte line are taken `dist` elements apart: blocks of per_line * dist rows,
// inside a block row (j % dist) * per_line + j / dist. dist <= 1: natural order. The ragged tail keeps its natural position.
__device__ inline uint64_t row_of(uint64_t e_row, uint64_t rows, uint64_t per_line, uint64_t dist) {
	if(dist <= 1 || per_line <= 1) return e_row;
	const uint64_t block = per_line * dist;
	if(e_row >= rows / block * block) return e_row;
	const uint64_t j = e_row % block;
	return e_row - j + (j % dist) * per_line + j / dist;
}

template <typename T> __device__ inline void store_nt(T* p, T v) {
	if constexpr(sizeof(T) <= 4) {
		__builtin_nontemporal_store(v, p);
	} else { // vector types: store the 4-byte words
		auto* w = reinterpret_cast<uint32_t*>(p);
		const auto* x = reinterpret_cast<const uint32_t*>(&v);
		for(unsigned q = 0; q < sizeof(T) / 4; ++q) __builtin_nontemporal_store(x[q], w + q);
	}
}

template <int E, bool Write, bool NT>
__global__ void copy_rows(std::byte* host, std::byte* dev, uint64_t rows, uint64_t S, uint64_t P, uint64_t dist, uint64_t per_line) {
	using T = typename elem_t<E>::type;
	const uint64_t per_row = S / E;
	const uint64_t n = rows * per_row;
	for(uint64_t i = blockIdx.x * uint64_t(blockDim.x) + threadIdx.x; i < n; i += uint64_t(gridDim.x) * blockDim.x) {
		const uint64_t r = row_of(i / per_row, rows, per_line, dist);
		const uint64_t k = i % per_row;
		T* h = reinterpret_cast<T*>(host + r * P + k * E);
		T* d = reinterpret_cast<T*>(dev + r * S + k * E);
		if constexpr(Write && NT) {
			store_nt(h, *d);
		} else if constexpr(Write) {
			*h = *d;
		} else {
			*d = *h;
		}
	}
}

// device -> host, one pass of a phased copy: the rows r with r % phases == phase (one row per 64-byte line when phases = rows per line)
template <int E>
__global__ void write_phase(std::byte* host, const std::byte* dev, uint64_t rows, uint64_t S, uint64_t P, uint64_t phase, uint64_t phases) {
	using T = typename elem_t<E>::type;
	const uint64_t per_row = S / E;
	const uint64_t n = (rows - phase + phases - 1) / phases * per_row;
	for(uint64_t i = blockIdx.x * uint64_t(blockDim.x) + threadIdx.x; i < n; i += uint64_t(gridDim.x) * blockDim.x) {
		const uint64_t r = i / per_row * phases + phase, k = i % per_row;
		*reinterpret_cast<T*>(host + r * P + k * E) = *reinterpret_cast<const T*>(dev + r * S + k * E);
	}
}

// device -> host as in the proposed copylib change: `slots` launches over the whole grid, each writing only the rows r with
// r % slots == slot (the other work items skip their element)
template <int E>
__global__ void write_filter(std::byte* host, const std::byte* dev, uint64_t rows, uint64_t S, uint64_t P, uint64_t slot, uint64_t slots) {
	using T = typename elem_t<E>::type;
	const uint64_t per_row = S / E;
	const uint64_t n = rows * per_row;
	for(uint64_t i = blockIdx.x * uint64_t(blockDim.x) + threadIdx.x; i < n; i += uint64_t(gridDim.x) * blockDim.x) {
		const uint64_t r = i / per_row, k = i % per_row;
		if(r % slots != slot) continue;
		*reinterpret_cast<T*>(host + r * P + k * E) = *reinterpret_cast<const T*>(dev + r * S + k * E);
	}
}

// device -> host by whole 16-byte pieces: read the host piece, put in the row bytes it contains, write the piece back
__global__ void write_rmw(std::byte* host, const std::byte* dev, uint64_t rows, uint64_t S, uint64_t P) {
	const uint64_t pieces = (rows * P + 15) / 16;
	for(uint64_t j = blockIdx.x * uint64_t(blockDim.x) + threadIdx.x; j < pieces; j += uint64_t(gridDim.x) * blockDim.x) {
		uint4 v = reinterpret_cast<uint4*>(host)[j];
		auto* w = reinterpret_cast<uint32_t*>(&v);
		for(int q = 0; q < 4; ++q) { // 4-byte words; S and P are multiples of 4 for this mode
			const uint64_t b = j * 16 + q * 4;
			const uint64_t r = b / P, off = b % P;
			if(r < rows && off < S) w[q] = *reinterpret_cast<const uint32_t*>(dev + r * S + off);
		}
		reinterpret_cast<uint4*>(host)[j] = v;
	}
}

template <int E>
void launch(bool write, std::byte* host, std::byte* dev, uint64_t rows, uint64_t S, uint64_t P, uint64_t dist, int wg, int items, bool nt) {
	const uint64_t per_line = P < 64 ? 64 / P : 1;
	const uint64_t n = rows * (S / E);
	const uint64_t threads = (n + items - 1) / items;
	const unsigned grid = static_cast<unsigned>(std::min<uint64_t>((threads + wg - 1) / wg, 1u << 30));
	if(write && nt) {
		copy_rows<E, true, true><<<grid, wg>>>(host, dev, rows, S, P, dist, per_line);
	} else if(write) {
		copy_rows<E, true, false><<<grid, wg>>>(host, dev, rows, S, P, dist, per_line);
	} else {
		copy_rows<E, false, false><<<grid, wg>>>(host, dev, rows, S, P, dist, per_line);
	}
}

int main(int argc, char** argv) {
	if(argc < 6) {
		std::fprintf(stderr, "usage: %s <r|w> <S> <P> <E> <rows> [alloc] [order] [reps] [wg] [items]\n", argv[0]);
		return 1;
	}
	const bool write = argv[1][0] == 'w';
	const uint64_t S = std::strtoull(argv[2], nullptr, 10), P = std::strtoull(argv[3], nullptr, 10);
	const int E = std::atoi(argv[4]);
	const uint64_t rows = std::strtoull(argv[5], nullptr, 10);
	const std::string alloc = argc > 6 ? argv[6] : "default", order = argc > 7 ? argv[7] : "natural";
	const int reps = argc > 8 ? std::atoi(argv[8]) : 3, wg = argc > 9 ? std::atoi(argv[9]) : 256, items = argc > 10 ? std::atoi(argv[10]) : 1;
	const bool nt = argc > 11 && std::string(argv[11]) == "nt";
	if(S == 0 || S > P || S % E || P % E || (order == "rmw" && (!write || S % 4 || P % 4)) || ((order == "phase" || order == "filter") && !write)) {
		std::fprintf(stderr, "invalid S/P/E/order\n");
		return 1;
	}
	const uint64_t host_bytes = (rows * P + 15) / 16 * 16, dev_bytes = rows * S;

	std::byte* host = nullptr;
	if(alloc == "register") {
		host = static_cast<std::byte*>(std::aligned_alloc(4096, (host_bytes + 4095) / 4096 * 4096));
		CHECK(hipHostRegister(host, (host_bytes + 4095) / 4096 * 4096, hipHostRegisterDefault));
	} else {
		const unsigned flags = alloc == "coherent" ? hipHostMallocCoherent : alloc == "noncoherent" ? hipHostMallocNonCoherent
		    : alloc == "wc" ? hipHostMallocWriteCombined : hipHostMallocDefault;
		CHECK(hipHostMalloc(reinterpret_cast<void**>(&host), host_bytes, flags));
	}
	std::byte* dev = nullptr;
	CHECK(hipMalloc(reinterpret_cast<void**>(&dev), dev_bytes));

	// host: row bytes = f(row, offset), gap bytes = 0xee; device: the other copy's pattern (so a missing copy fails the check)
	const auto value = [](uint64_t r, uint64_t o) { return std::byte(static_cast<uint8_t>(r * 131 + o * 7 + 1)); };
	std::vector<std::byte> dev_init(dev_bytes);
	for(uint64_t r = 0; r < rows; ++r)
		for(uint64_t o = 0; o < S; ++o) dev_init[r * S + o] = write ? value(r, o) : std::byte(0);
	std::memset(host, 0xee, host_bytes);
	if(!write)
		for(uint64_t r = 0; r < rows; ++r)
			for(uint64_t o = 0; o < S; ++o) host[r * P + o] = value(r, o);
	CHECK(hipMemcpy(dev, dev_init.data(), dev_bytes, hipMemcpyHostToDevice));

	hipEvent_t start, stop;
	CHECK(hipEventCreate(&start));
	CHECK(hipEventCreate(&stop));
	std::vector<double> gbps;
	for(int rep = 0; rep <= reps; ++rep) {
		CHECK(hipDeviceSynchronize());
		CHECK(hipEventRecord(start));
		if(order == "phase") { // per_line launches on one stream, each writing one row per 64-byte line
			const uint64_t phases = P < 64 ? 64 / P : 1;
			for(uint64_t ph = 0; ph < phases && ph < rows; ++ph) {
				const uint64_t n = (rows - ph + phases - 1) / phases * (S / E);
				const unsigned grid = static_cast<unsigned>(std::min<uint64_t>((n + wg - 1) / wg, 1u << 30));
				switch(E) {
				case 4: write_phase<4><<<grid, wg>>>(host, dev, rows, S, P, ph, phases); break;
				case 8: write_phase<8><<<grid, wg>>>(host, dev, rows, S, P, ph, phases); break;
				case 16: write_phase<16><<<grid, wg>>>(host, dev, rows, S, P, ph, phases); break;
				default: std::fprintf(stderr, "phase: E must be 4, 8 or 16\n"); return 1;
				}
			}
		} else if(order == "filter") { // the proposed copylib change: (62 + S) / P + 1 launches if S < P < 64, else one
			const uint64_t slots = S < P && P < 64 ? (62 + S) / P + 1 : 1;
			const uint64_t n = rows * (S / E);
			const unsigned grid = static_cast<unsigned>(std::min<uint64_t>((n + wg - 1) / wg, 1u << 30));
			for(uint64_t sl = 0; sl < slots; ++sl) {
				switch(E) {
				case 4: write_filter<4><<<grid, wg>>>(host, dev, rows, S, P, sl, slots); break;
				case 8: write_filter<8><<<grid, wg>>>(host, dev, rows, S, P, sl, slots); break;
				case 16: write_filter<16><<<grid, wg>>>(host, dev, rows, S, P, sl, slots); break;
				default: std::fprintf(stderr, "filter: E must be 4, 8 or 16\n"); return 1;
				}
			}
		} else if(order == "rmw") {
			const uint64_t pieces = host_bytes / 16;
			write_rmw<<<static_cast<unsigned>(std::min<uint64_t>((pieces + wg - 1) / wg, 1u << 30)), wg>>>(host, dev, rows, S, P);
		} else {
			// natural: dist 1; spread: every line apart; d<D>: D elements apart
			const uint64_t per_line = P < 64 ? 64 / P : 1;
			const uint64_t dist = order == "spread" ? rows / per_line : order[0] == 'd' ? std::strtoull(order.c_str() + 1, nullptr, 10) : 1;
			switch(E) {
			case 1: launch<1>(write, host, dev, rows, S, P, dist, wg, items, nt); break;
			case 2: launch<2>(write, host, dev, rows, S, P, dist, wg, items, nt); break;
			case 4: launch<4>(write, host, dev, rows, S, P, dist, wg, items, nt); break;
			case 8: launch<8>(write, host, dev, rows, S, P, dist, wg, items, nt); break;
			case 16: launch<16>(write, host, dev, rows, S, P, dist, wg, items, nt); break;
			default: std::fprintf(stderr, "E must be 1, 2, 4, 8 or 16\n"); return 1;
			}
		}
		CHECK(hipGetLastError());
		CHECK(hipEventRecord(stop));
		CHECK(hipEventSynchronize(stop));
		float ms = 0;
		CHECK(hipEventElapsedTime(&ms, start, stop));
		if(rep > 0) gbps.push_back(double(rows * S) / (ms * 1e-3) / 1e9);
	}

	bool ok = true;
	if(write) {
		for(uint64_t r = 0; r < rows && ok; ++r)
			for(uint64_t o = 0; o < P && ok; ++o)
				if(host[r * P + o] != (o < S ? value(r, o) : std::byte(0xee))) ok = false;
	} else {
		std::vector<std::byte> back(dev_bytes);
		CHECK(hipMemcpy(back.data(), dev, dev_bytes, hipMemcpyDeviceToHost));
		for(uint64_t r = 0; r < rows && ok; ++r)
			for(uint64_t o = 0; o < S && ok; ++o)
				if(back[r * S + o] != value(r, o)) ok = false;
	}
	std::sort(gbps.begin(), gbps.end());
	const double med = gbps[gbps.size() / 2];
	hipDeviceProp_t prop;
	CHECK(hipGetDeviceProperties(&prop, 0));
	std::printf("hk_probe dir=%s S=%lu P=%lu E=%d rows=%lu alloc=%s order=%s wg=%d items=%d store=%s device=%s l2=%dKiB\n", write ? "w" : "r",
	    (unsigned long)S, (unsigned long)P, E, (unsigned long)rows, alloc.c_str(), order.c_str(), wg, items, nt ? "nt" : "plain", prop.gcnArchName,
	    prop.l2CacheSize / 1024);
	std::printf("probe: %.4fGB/s rows/s=%.1fM check=%s\n", med, med * 1e9 / S / 1e6, ok ? "ok" : "FAILED");
	if(alloc == "register") {
		CHECK(hipHostUnregister(host));
		std::free(host);
	} else {
		CHECK(hipHostFree(host));
	}
	CHECK(hipFree(dev));
	return ok ? 0 : 2;
}
