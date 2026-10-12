// One memcpy of a run-time length n (argv[1]), single-stepped in gdb by trace_memcpy.gdb. The second call is traced, when the
// symbol is already bound (the binary is linked with -z now, so there is no lazy binding either).
#include <cstdlib>
#include <cstring>

__attribute__((noinline)) void copy_one(void* d, const void* s, size_t n) { std::memcpy(d, s, n); }

int main(int argc, char** argv) {
	const size_t n = std::atoi(argv[1]);
	alignas(64) static char src[256], dst[256];
	copy_one(dst, src, n);
	copy_one(dst + 64, src + 64, n);
	return dst[0];
}
