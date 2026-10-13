// Celerity Throughput Benchmark Application
// Measures host->device, device compute, and device->host throughput

#include <chrono>
#include <cstdint>
#include <hip/amd_detail/amd_hip_runtime.h>
#include <iomanip>
#include <iostream>

#include <hip/hip_runtime.h>

#include "helpers.h"

//using namespace celerity;

constexpr size_t coarsening_fac = 1;

int main(int argc, char* argv[]) {
    const uint64_t data_size = (argc > 1) ? std::stoul(argv[1]) : 32*32*1024*1024; // elements

    std::cout << "Data size: " << data_size << " elements" << std::endl;

    Measurement timing_memcpy("copy host to device");
    Measurement timing_buffer_creation("buffer creation");
    Measurement timing_memcpy_profiling("profiling info for copy host to device");

//    hipInit(0);
    // Initialize runtime
//    celerity::queue queue;

    timing_buffer_creation.measureStart();
//    sycl::buffer<std::uint32_t, 1> buf((sycl::range<1>(data_size)));
    void *devPtr;
    int32_t *hostPtr;
    hipMalloc(&devPtr, data_size*sizeof(int32_t));

    hipError_t hError = hipHostMalloc((void**)&hostPtr, data_size*sizeof(int32_t), 0);
    for(int i = 0; i < data_size; ++i){
        hostPtr[i] = 1;
    }
    timing_buffer_creation.measureEnd();

    hipEvent_t start, stop;
    hipEventCreate(&start);
    hipEventCreate(&stop);

    hipEventRecord(start, NULL);

    // Kernel execution benchmark
//    timing_memcpy.measureStart();
    hipMemcpyHtoD(devPtr, hostPtr, data_size*sizeof(int32_t));
//    timing_memcpy.measureEnd();
    hipEventRecord(stop, NULL);
    hipEventSynchronize(stop);
    
    float eventMs = 1;
    if(hipEventElapsedTime(&eventMs, start, stop)){
        fprintf(stderr, "error reading timing\n");
    }else{
        printf("event took %f ms\n", eventMs);
    };
    timing_memcpy.start = std::chrono::steady_clock::time_point(std::chrono::nanoseconds(0));
    timing_memcpy.end = std::chrono::steady_clock::time_point(std::chrono::nanoseconds((int64_t)(1000000*eventMs)));

//    uint64_t start_profiling = ev.get_profiling_info<sycl::info::event_profiling::command_start>();
//    uint64_t end_profiling = ev.get_profiling_info<sycl::info::event_profiling::command_end>();

//    timing_memcpy_profiling.start = std::chrono::steady_clock::time_point(std::chrono::nanoseconds(start_profiling));
//    timing_memcpy_profiling.end = std::chrono::steady_clock::time_point(std::chrono::nanoseconds(end_profiling));

    std::cout << std::setprecision(std::numeric_limits<double>::max_digits10)<< std::fixed;
    std::cout << "\n=== Benchmark Results ===\n";
    uint64_t bytes = (uint64_t) data_size * sizeof(uint32_t);
    
    std::cout << "Data Size: " << (double) bytes / (1024*1024*1024) << "GiB\n";
    timing_buffer_creation.printTimeWithGBpS(bytes);
    timing_memcpy.printTimeWithGBpS(bytes);
    timing_memcpy_profiling.printTimeWithGBpS(bytes);

    return 0;
}
