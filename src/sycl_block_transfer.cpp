// Celerity Throughput Benchmark Application
// Measures host->device, device compute, and device->host throughput

#include <sycl/sycl.hpp>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <iostream>

#include "helpers.h"
//using namespace celerity;

constexpr size_t coarsening_fac = 1;

int main(int argc, char* argv[]) {
    const uint64_t data_size = (argc > 1) ? std::stoul(argv[1]) : 32*32*1024*1024; // elements

    std::cout << "Data size: " << data_size << " elements" << std::endl;

    Measurement timing_memcpy("copy host to device");
    Measurement timing_buffer_creation("buffer creation");
    Measurement timing_memcpy_profiling("profiling info for copy host to device");

    // Initialize runtime
    sycl::property_list properties{sycl::property::queue::enable_profiling()};
    sycl::queue queue(properties);
//    celerity::queue queue;
    void* devBuffer = sycl::aligned_alloc_device(1024, data_size * sizeof(int32_t), queue);
    int32_t* hostBuffer = (int32_t*) sycl::aligned_alloc_host(1024, data_size * sizeof(int32_t), queue);

    timing_buffer_creation.measureStart();
//    sycl::buffer<std::uint32_t, 1> buf((sycl::range<1>(data_size)));

    for(int i = 0; i < data_size; ++i){
        hostBuffer[i] = 1;
    }
    timing_buffer_creation.measureEnd();

    // Kernel execution benchmark
    queue.wait();
    timing_memcpy.measureStart();
/*    queue.submit([&](sycl::handler& cgh) {
        sycl::accessor acc(buf, cgh, sycl::read_write);

        cgh.parallel_for<class throughput_kernel>(sycl::range<1>(data_size),[=](sycl::item<1> item) {
            if(acc[item] == 3){
                acc[item] = 2;
            };
        });
    });
*/
    auto ev = queue.memcpy(devBuffer, hostBuffer, data_size*sizeof(uint32_t));
    ev.wait();
//    queue.wait();

    timing_memcpy.measureEnd();
    uint64_t start_profiling = ev.get_profiling_info<sycl::info::event_profiling::command_start>();
    uint64_t end_profiling = ev.get_profiling_info<sycl::info::event_profiling::command_end>();

    timing_memcpy_profiling.start = std::chrono::steady_clock::time_point(std::chrono::nanoseconds(start_profiling));
    timing_memcpy_profiling.end = std::chrono::steady_clock::time_point(std::chrono::nanoseconds(end_profiling));

    std::cout << std::setprecision(std::numeric_limits<double>::max_digits10)<< std::fixed;
    std::cout << "copy event profiling result: " << (end_profiling-start_profiling) << "ns\n";
    std::cout << "\n=== Benchmark Results ===\n";
    uint64_t bytes = (uint64_t) data_size * sizeof(uint32_t);
    
    std::cout << "Data Size: " << (double) bytes / (1024*1024*1024) << "GiB\n";
    timing_buffer_creation.printTimeWithGBpS(bytes);
    timing_memcpy.printTimeWithGBpS(bytes);
    timing_memcpy_profiling.printTimeWithGBpS(bytes);

    return 0;
}
