#include <CL/cl.h>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <iomanip>
#include <vector>
#include "helpers.h"
#include "clu_errcheck.h"

const char* kernelSource = R"CLC(
__kernel void check_and_zero(__global int* data) {
    int id = get_global_id(0);
    if (data[id] == 4) {
        data[id] = 0;
    }
}
)CLC";

int main(int argc, char* argv[]) {

    const uint64_t data_size = (argc > 1) ? std::stoul(argv[1]) : 1024*1024*1024; // elements

    std::cout << "Data size: " << data_size << " elements" << std::endl;

    std::cout << "Setting up host data\n";

    Measurement timing_buffer_creation("buffer creation");
    Measurement timing_memcpy_profiling("profiling info for copy host to device");

    std::vector<std::uint32_t> host_data;
    host_data.reserve(data_size);

    for(size_t i = 0; i < data_size; i++){
        host_data.emplace_back(1);
    }
    std::cout << "Done setting up host data\n";

    cl_int err;

    // Platform
    cl_platform_id platform;
    clGetPlatformIDs(1, &platform, nullptr);

    // Device
    cl_device_id device;
    clGetDeviceIDs(platform, CL_DEVICE_TYPE_DEFAULT, 1, &device, nullptr);

    // Context
    cl_context context = clCreateContext(nullptr, 1, &device, nullptr, nullptr, &err);
    CLU_ERRCHECK(err);

    // Queue
    cl_queue_properties properties[] = {
        CL_QUEUE_PROPERTIES, CL_QUEUE_PROFILING_ENABLE,  // enable profiling
        0                                               // terminator
    };
    cl_command_queue queue = clCreateCommandQueueWithProperties(context, device, properties, &err);
    CLU_ERRCHECK(err);

    timing_buffer_creation.measureStart();
    // Buffer
    cl_mem buffer = clCreateBuffer(
        context,
        CL_MEM_READ_WRITE | CL_MEM_COPY_HOST_PTR,
        sizeof(uint32_t) * data_size,
        host_data.data(),
        &err
    );
    CLU_ERRCHECK(err);
    timing_buffer_creation.measureEnd();

    cl_event writeBufferEvent;
    clEnqueueWriteBuffer(queue, buffer, CL_TRUE, 0, data_size * sizeof(uint32_t), host_data.data(), 0, NULL, &writeBufferEvent);
    CLU_ERRCHECK(err);

    clWaitForEvents(1, &writeBufferEvent);

    cl_ulong timeStart, timeEnd;
    clGetEventProfilingInfo(writeBufferEvent, CL_PROFILING_COMMAND_START, sizeof(cl_ulong), &timeStart, nullptr);
    clGetEventProfilingInfo(writeBufferEvent, CL_PROFILING_COMMAND_END, sizeof(cl_ulong), &timeEnd, nullptr);
    timing_memcpy_profiling.start=std::chrono::steady_clock::time_point(std::chrono::nanoseconds(timeStart));
    timing_memcpy_profiling.end=std::chrono::steady_clock::time_point(std::chrono::nanoseconds(timeEnd));

    std::cout << std::setprecision(std::numeric_limits<double>::max_digits10)<< std::fixed;
    auto bytes = data_size * sizeof(std::uint32_t);
    std::cout << "Data Size: " << (double) bytes / (1024*1024*1024) << "GiB\n";
    timing_memcpy_profiling.printTimeWithGBpS(bytes);
//    cl_ulong durationNs = (timeEnd - timeStart);
//    std::cout << "Kernel execution time: " << durationNs << " ns" << std::endl;
//
//    double gbPerSec = (double) (data_size * sizeof(std::uint32_t)) / (double) durationNs;
//    std::cout << "Effective memory bandwidth: " << gbPerSec << " GB/s" << std::endl;
    // Cleanup
    clReleaseMemObject(buffer);
//    clReleaseKernel(kernel);
//    clReleaseProgram(program);
    clReleaseCommandQueue(queue);
    clReleaseContext(context);
}