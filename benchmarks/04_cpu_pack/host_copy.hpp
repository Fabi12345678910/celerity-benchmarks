// Fast host <-> host copies for copylib's staging step. Drop-in replacement for
//   for_each_copy_run(spec, [&](int64_t s, int64_t t, int64_t n) { std::memcpy(target.base_ptr() + t, source.base_ptr() + s, n); });
// that copies the same bytes in the same order, but
//  - computes a side's position with divisions only once, at the window start, and then only advances pointers, and
//  - copies the rows of a strided side against a contiguous side (packing into / unpacking from staging) with a loop specialized
//    for the row width, so that each row is one load and one store instead of a memcpy call.
#pragma once

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <cstring>

#include "copylib/core.hpp"

namespace copylib::detail {

// One side of a copy, walked in packed order: the current address, the bytes left in the current row, the rows left in the current
// plane, and the jumps from one byte past a row to the next row and from one byte past a plane's last row to the next plane.
struct host_cursor {
	std::byte* ptr;
	int64_t row_bytes;
	int64_t left_in_row;
	int64_t rows_per_plane;
	int64_t rows_left; // rows left in the current plane, the current one included
	int64_t row_jump;
	int64_t plane_jump;

	explicit host_cursor(const data_layout& l) {
		const int64_t w = l.d0_end_offset - l.d0_start_offset;
		const int64_t h = l.d1_end_offset - l.d1_start_offset;
		const int64_t i0 = l.start % w;
		const int64_t i1 = l.start / w % h;
		const int64_t i2 = l.start / w / h;
		// the same address as l.base_ptr() + l.offset_at(l.start)
		ptr = l.base_ptr() + ((i2 + l.d2_start_offset) * l.d1_stride + i1 + l.d1_start_offset) * l.d0_stride + l.d0_start_offset + i0;
		row_bytes = w;
		left_in_row = w - i0;
		rows_per_plane = h;
		rows_left = h - i1;
		row_jump = l.d0_stride - w;
		plane_jump = (l.d1_stride - h + 1) * l.d0_stride - w;
	}

	// the window lies within a single row, i.e. this side is contiguous
	[[nodiscard]] bool contiguous(int64_t length) const { return left_in_row >= length; }

	void advance(int64_t n) {
		ptr += n;
		left_in_row -= n;
		if(left_in_row == 0) {
			left_in_row = row_bytes;
			if(--rows_left == 0) {
				rows_left = rows_per_plane;
				ptr += plane_jump;
			} else {
				ptr += row_jump;
			}
		}
	}
};

// Copies `rows` whole rows of W bytes between the strided cursor (at a row start) and the contiguous pointer.
// Pack: strided -> contiguous; otherwise contiguous -> strided. Planes are crossed with the cursor's plane jump.
template <int64_t W, bool Pack>
void copy_full_rows(host_cursor& strided, std::byte*& contiguous, int64_t rows) {
	const int64_t pitch = strided.row_jump + W;
	std::byte* s = strided.ptr;
	std::byte* c = contiguous;
	while(rows > 0) {
		const int64_t n = std::min(rows, strided.rows_left);
		for(int64_t r = 0; r < n; ++r) {
			if constexpr(Pack) {
				std::memcpy(c, s, W);
			} else {
				std::memcpy(s, c, W);
			}
			s += pitch;
			c += W;
		}
		rows -= n;
		strided.rows_left -= n;
		if(strided.rows_left == 0) {
			strided.rows_left = strided.rows_per_plane;
			s += strided.plane_jump - strided.row_jump;
		}
	}
	strided.ptr = s;
	contiguous = c;
}

template <bool Pack>
void copy_full_rows_any(host_cursor& strided, std::byte*& contiguous, int64_t rows) {
	switch(strided.row_bytes) {
	case 1: return copy_full_rows<1, Pack>(strided, contiguous, rows);
	case 2: return copy_full_rows<2, Pack>(strided, contiguous, rows);
	case 4: return copy_full_rows<4, Pack>(strided, contiguous, rows);
	case 8: return copy_full_rows<8, Pack>(strided, contiguous, rows);
	case 12: return copy_full_rows<12, Pack>(strided, contiguous, rows);
	case 16: return copy_full_rows<16, Pack>(strided, contiguous, rows);
	case 24: return copy_full_rows<24, Pack>(strided, contiguous, rows);
	case 32: return copy_full_rows<32, Pack>(strided, contiguous, rows);
	case 64: return copy_full_rows<64, Pack>(strided, contiguous, rows);
	default: break;
	}
	// other widths: the same loop with memcpy of a runtime length, which is cheap relative to rows of more than about 64 bytes
	const int64_t w = strided.row_bytes;
	const int64_t pitch = strided.row_jump + w;
	std::byte* s = strided.ptr;
	std::byte* c = contiguous;
	while(rows > 0) {
		const int64_t n = std::min(rows, strided.rows_left);
		for(int64_t r = 0; r < n; ++r) {
			if constexpr(Pack) {
				std::memcpy(c, s, static_cast<size_t>(w));
			} else {
				std::memcpy(s, c, static_cast<size_t>(w));
			}
			s += pitch;
			c += w;
		}
		rows -= n;
		strided.rows_left -= n;
		if(strided.rows_left == 0) {
			strided.rows_left = strided.rows_per_plane;
			s += strided.plane_jump - strided.row_jump;
		}
	}
	strided.ptr = s;
	contiguous = c;
}

inline void copy_host_to_host(const copy_spec& spec) {
	int64_t remaining = spec.source_layout.window_length();
	if(remaining == 0) return;
	host_cursor src(spec.source_layout);
	host_cursor dst(spec.target_layout);

	// one run: the bytes until the next row end of either side (also the general case, e.g. rows of different widths on both sides)
	const auto step = [&] {
		const int64_t n = std::min({src.left_in_row, dst.left_in_row, remaining});
		std::memcpy(dst.ptr, src.ptr, static_cast<size_t>(n));
		src.advance(n);
		dst.advance(n);
		remaining -= n;
	};

	const bool src_contiguous = src.contiguous(remaining);
	const bool dst_contiguous = dst.contiguous(remaining);
	if(src_contiguous && dst_contiguous) {
		std::memcpy(dst.ptr, src.ptr, static_cast<size_t>(remaining));
		return;
	}
	if(src_contiguous || dst_contiguous) {
		// staging: one side contiguous, so every run is a row of the strided side; a partial first and last row go through step()
		host_cursor& strided = src_contiguous ? dst : src;
		host_cursor& contiguous = src_contiguous ? src : dst;
		if(strided.left_in_row != strided.row_bytes) step();
		const int64_t rows = remaining / strided.row_bytes;
		if(rows > 0) {
			if(src_contiguous) {
				copy_full_rows_any<false>(strided, contiguous.ptr, rows);
			} else {
				copy_full_rows_any<true>(strided, contiguous.ptr, rows);
			}
			contiguous.left_in_row -= rows * strided.row_bytes;
			remaining -= rows * strided.row_bytes;
		}
		if(remaining > 0) step();
		return;
	}
	while(remaining > 0) step();
}

} // namespace copylib::detail
