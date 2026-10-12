// Runs one variant of copy_loops.cpp on a pack of `rows` 4-byte rows with a pitch of 8 bytes (cpu_pack's layout with M = 2);
// trace_rows.gdb counts every instruction measured() executes, memcpy included. Usage: trace_rows <variant> <rows>
#include <copylib/core.hpp>

#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>

using namespace copylib;

void copy_copylib(const copy_spec& spec);
void rows_runtime(std::byte* dst, int64_t dst_stride, const std::byte* src, int64_t src_stride, int64_t rows, int64_t width);
void rows_fixed4(std::byte* dst, int64_t dst_stride, const std::byte* src, int64_t src_stride, int64_t rows);
void pack_var(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch, int64_t w);
void pack_fixed4(std::byte* c, const std::byte* s, int64_t rows, int64_t pitch);

constexpr int64_t pitch = 8;

extern "C" __attribute__((noinline)) void measured(int v, const copy_spec& spec, std::byte* dst, const std::byte* src, int64_t rows) {
	switch(v) {
	case 0: copy_copylib(spec); break;
	case 1: rows_runtime(dst, 4, src, pitch, rows, 4); break;
	case 2: rows_fixed4(dst, 4, src, pitch, rows); break;
	case 3: pack_var(dst, src, rows, pitch, 4); break;
	default: pack_fixed4(dst, src, rows, pitch); break;
	}
}

int main(int argc, char** argv) {
	const char* names[] = {"copylib", "rows_runtime", "rows_fixed4", "pack_var", "pack_fixed4"};
	int v = 0;
	while(v < 4 && std::strcmp(argv[1], names[v]) != 0) ++v;
	const int64_t rows = std::atoll(argv[2]);
	std::vector<std::byte> host(rows * pitch), staging(rows * 4);
	const data_layout host_layout(reinterpret_cast<intptr_t>(host.data()), pitch, rows, 0, 0, 0, 4, rows, 1);
	const copy_spec spec(device_id::host, host_layout.with_window(0, rows * 4), device_id::host,
	    data_layout(reinterpret_cast<intptr_t>(staging.data()), 0, rows * 4));
	measured(v, spec, staging.data(), host.data(), rows);
	return static_cast<int>(staging[0]);
}
