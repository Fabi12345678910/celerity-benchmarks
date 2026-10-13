// The CPU loops of copylib's staged copies (packing the strided host side into contiguous staging), compiled to assembly for
// comparison, see README.md. The functions are the variants measured by cpu_pack (../cpu_pack.cpp) and the row loop of the proposed
// copylib::detail::copy_full_rows (../host_copy.hpp), each as a separate non-template function so that its code has its own label.
#include <copylib/core.hpp>

#include <cstddef>
#include <cstdint>
#include <cstring>

using namespace copylib;

// copylib today: execute_copy's host <-> host path (gpu3dcopylib src/backend.cpp), cpu_pack "copylib"
void copy_copylib(const copy_spec& spec) {
	const auto& source = spec.source_layout;
	const auto& target_layout = spec.target_layout;
	for_each_copy_run(spec, [&](int64_t source_offset, int64_t target_offset, int64_t length) {
		std::memcpy(target_layout.base_ptr() + target_offset, source.base_ptr() + source_offset, length);
	});
}

// cpu_pack "rowloop": one memcpy per row, the row width as a run-time length
void rows_runtime(std::byte* dst, int64_t dst_stride, const std::byte* src, int64_t src_stride, int64_t rows, int64_t width) {
	for(int64_t r = 0; r < rows; ++r) {
		std::memcpy(dst + r * dst_stride, src + r * src_stride, static_cast<size_t>(width));
	}
}

// cpu_pack "fixed": the same loop with the row width as a compile-time constant
template <int64_t W>
void rows_fixed(std::byte* dst, int64_t dst_stride, const std::byte* src, int64_t src_stride, int64_t rows) {
	for(int64_t r = 0; r < rows; ++r) {
		std::memcpy(dst + r * dst_stride, src + r * src_stride, W);
	}
}

void rows_fixed4(std::byte* dst, int64_t dst_stride, const std::byte* src, int64_t src_stride, int64_t rows) {
	rows_fixed<4>(dst, dst_stride, src, src_stride, rows);
}

// host_copy.hpp copy_full_rows (proposal), packing within one plane: the strided side advances by its pitch, the contiguous side
// by the row width. pack_var is the default branch of copy_full_rows_any (widths without a specialization).
void pack_var(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch, int64_t w) {
	for(int64_t r = 0; r < rows; ++r) {
		std::memcpy(c, s, static_cast<size_t>(w));
		s += pitch;
		c += w;
	}
}

template <int64_t W>
void pack_fixed(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch) {
	for(int64_t r = 0; r < rows; ++r) {
		std::memcpy(c, s, W);
		s += pitch;
		c += W;
	}
}

void pack_fixed4(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch) { pack_fixed<4>(c, s, rows, pitch); }
void pack_fixed8(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch) { pack_fixed<8>(c, s, rows, pitch); }
void pack_fixed12(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch) { pack_fixed<12>(c, s, rows, pitch); }
void pack_fixed16(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch) { pack_fixed<16>(c, s, rows, pitch); }
void pack_fixed64(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch) { pack_fixed<64>(c, s, rows, pitch); }
