// OpenCL 1.2 C API: one in-order command queue, one cl_mem per buffer, clEnqueueNDRangeKernel.
// Device selection: OPENCL_PLATFORM / OPENCL_DEVICE (indices, default 0 / first GPU device).
#define CL_TARGET_OPENCL_VERSION 120
#include "bench_common.h"

#include <CL/cl.h>

#include <vector>

#define CL_CHECK(expr)                                                                                                                                         \
	do {                                                                                                                                                       \
		const cl_int err_ = (expr);                                                                                                                            \
		if(err_ != CL_SUCCESS) {                                                                                                                               \
			std::fprintf(stderr, "%s:%d: %s failed: %d\n", __FILE__, __LINE__, #expr, err_);                                                                   \
			std::exit(1);                                                                                                                                      \
		}                                                                                                                                                      \
	} while(0)

static const char* kernel_source = "__kernel void increment_kernel(__global int* p, const ulong n) {\n"
                                   "  size_t i = get_global_id(0);\n"
                                   "  if(i < n) p[i] += 1;\n"
                                   "}\n";

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

	cl_int err = CL_SUCCESS;
	cl_context ctx = clCreateContext(nullptr, 1, &device, nullptr, nullptr, &err);
	CL_CHECK(err);
	cl_command_queue queue = clCreateCommandQueue(ctx, device, 0, &err); // in-order by default
	CL_CHECK(err);
	cl_program program = clCreateProgramWithSource(ctx, 1, &kernel_source, nullptr, &err);
	CL_CHECK(err);
	if(clBuildProgram(program, 1, &device, nullptr, nullptr, nullptr) != CL_SUCCESS) {
		size_t log_size = 0;
		clGetProgramBuildInfo(program, device, CL_PROGRAM_BUILD_LOG, 0, nullptr, &log_size);
		std::vector<char> log(log_size + 1);
		clGetProgramBuildInfo(program, device, CL_PROGRAM_BUILD_LOG, log_size, log.data(), nullptr);
		std::fprintf(stderr, "build failed:\n%s\n", log.data());
		return 1;
	}
	cl_kernel kernel = clCreateKernel(program, "increment_kernel", &err);
	CL_CHECK(err);

	std::vector<cl_mem> bufs(c.buffers);
	const std::vector<int> zeros(c.elems, 0);
	for(auto& b : bufs) {
		b = clCreateBuffer(ctx, CL_MEM_READ_WRITE, c.elems * sizeof(int), nullptr, &err);
		CL_CHECK(err);
		CL_CHECK(clEnqueueWriteBuffer(queue, b, CL_TRUE, 0, c.elems * sizeof(int), zeros.data(), 0, nullptr, nullptr));
	}

	const cl_ulong n = c.elems;
	const size_t global = c.elems;
	bench::tally tally(c.buffers);
	bench::run_protocol(
	    c, tally,
	    [&](const size_t i) {
		    cl_mem buf = bufs[tally.buffer_for_task(i)];
		    CL_CHECK(clSetKernelArg(kernel, 0, sizeof(cl_mem), &buf));
		    CL_CHECK(clSetKernelArg(kernel, 1, sizeof(cl_ulong), &n));
		    CL_CHECK(clEnqueueNDRangeKernel(queue, kernel, 1, nullptr, &global, nullptr, 0, nullptr, nullptr));
	    },
	    [&] { CL_CHECK(clFinish(queue)); });

	bool ok = true;
	std::vector<int> host(c.elems);
	for(size_t b = 0; b < c.buffers; ++b) {
		CL_CHECK(clEnqueueReadBuffer(queue, bufs[b], CL_TRUE, 0, c.elems * sizeof(int), host.data(), 0, nullptr, nullptr));
		for(const int v : host) ok &= v == tally.expected(b);
	}
	for(auto b : bufs) clReleaseMemObject(b);
	clReleaseKernel(kernel);
	clReleaseProgram(program);
	clReleaseCommandQueue(queue);
	clReleaseContext(ctx);
	bench::report_check(ok);
	return ok ? 0 : 1;
}
