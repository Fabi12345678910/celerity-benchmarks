// OpenCL 1.2 C API: one in-order command queue, one CL_MEM_READ_WRITE device buffer, non-blocking clEnqueueWriteBuffer / clEnqueueReadBuffer + clFinish.
// Host memory: pinned = the pointer of a CL_MEM_ALLOC_HOST_PTR buffer that stays mapped (the usual OpenCL way to get pinned memory),
// pageable = page-aligned malloc'd memory. Device selection: OPENCL_PLATFORM / OPENCL_DEVICE (indices, default 0 / first GPU device).
#define CL_TARGET_OPENCL_VERSION 120
#include "memcpy_common.h"

#include <CL/cl.h>

#define CL_CHECK(expr)                                                                                                                                         \
	do {                                                                                                                                                       \
		const cl_int err_ = (expr);                                                                                                                            \
		if(err_ != CL_SUCCESS) {                                                                                                                               \
			std::fprintf(stderr, "%s:%d: %s failed: %d\n", __FILE__, __LINE__, #expr, err_);                                                                   \
			std::exit(1);                                                                                                                                      \
		}                                                                                                                                                      \
	} while(0)

int main(int argc, char** argv) {
	const auto c = bench::parse_args("opencl", argc, argv);
	const size_t platform_idx = std::getenv("OPENCL_PLATFORM") ? std::strtoull(std::getenv("OPENCL_PLATFORM"), nullptr, 10) : 0;
	const size_t device_idx = std::getenv("OPENCL_DEVICE") ? std::strtoull(std::getenv("OPENCL_DEVICE"), nullptr, 10) : 0;
	const cl_device_type device_type = std::getenv("OPENCL_ANY_DEVICE") ? CL_DEVICE_TYPE_ALL : CL_DEVICE_TYPE_GPU;

	cl_uint num_platforms = 0;
	CL_CHECK(clGetPlatformIDs(0, nullptr, &num_platforms));
	std::vector<cl_platform_id> platforms(num_platforms);
	CL_CHECK(clGetPlatformIDs(num_platforms, platforms.data(), nullptr));
	if(platform_idx >= num_platforms) { std::fprintf(stderr, "no OpenCL platform %zu\n", platform_idx); return 1; }
	cl_uint num_devices = 0;
	CL_CHECK(clGetDeviceIDs(platforms[platform_idx], device_type, 0, nullptr, &num_devices));
	std::vector<cl_device_id> devices(num_devices);
	CL_CHECK(clGetDeviceIDs(platforms[platform_idx], device_type, num_devices, devices.data(), nullptr));
	if(device_idx >= num_devices) { std::fprintf(stderr, "no OpenCL device %zu\n", device_idx); return 1; }
	const cl_device_id device = devices[device_idx];

	cl_int err;
	cl_context ctx = clCreateContext(nullptr, 1, &device, nullptr, nullptr, &err);
	CL_CHECK(err);
	cl_command_queue queue = clCreateCommandQueue(ctx, device, 0, &err); // in-order by default
	CL_CHECK(err);
	cl_mem dev = clCreateBuffer(ctx, CL_MEM_READ_WRITE, c.bytes, nullptr, &err);
	CL_CHECK(err);

	unsigned char *src, *dst;
	if(c.pinned) {
		cl_mem host_src = clCreateBuffer(ctx, CL_MEM_READ_WRITE | CL_MEM_ALLOC_HOST_PTR, c.bytes, nullptr, &err);
		CL_CHECK(err);
		cl_mem host_dst = clCreateBuffer(ctx, CL_MEM_READ_WRITE | CL_MEM_ALLOC_HOST_PTR, c.bytes, nullptr, &err);
		CL_CHECK(err);
		src = static_cast<unsigned char*>(clEnqueueMapBuffer(queue, host_src, CL_TRUE, CL_MAP_READ | CL_MAP_WRITE, 0, c.bytes, 0, nullptr, nullptr, &err));
		CL_CHECK(err);
		dst = static_cast<unsigned char*>(clEnqueueMapBuffer(queue, host_dst, CL_TRUE, CL_MAP_READ | CL_MAP_WRITE, 0, c.bytes, 0, nullptr, nullptr, &err));
		CL_CHECK(err);
	} else {
		src = bench::alloc_pageable(c.bytes);
		dst = bench::alloc_pageable(c.bytes);
	}
	bench::fill_pattern(src, c.bytes);
	std::memset(dst, 0, c.bytes);

	const auto wait = [&] { CL_CHECK(clFinish(queue)); };
	const auto h2d = bench::measure(c.reps, [&] { CL_CHECK(clEnqueueWriteBuffer(queue, dev, CL_FALSE, 0, c.bytes, src, 0, nullptr, nullptr)); }, wait);
	const auto d2h = bench::measure(c.reps, [&] { CL_CHECK(clEnqueueReadBuffer(queue, dev, CL_FALSE, 0, c.bytes, dst, 0, nullptr, nullptr)); }, wait);

	bench::print_config(c, c.pinned ? "pinned" : "pageable");
	bench::print_result("H2D", c.bytes, h2d);
	bench::print_result("D2H", c.bytes, d2h);
	bench::report_check(bench::check_pattern(dst, c.bytes));
	return 0;
}
