// Celerity Throughput Benchmark Application
// Measures host->device, device compute, and device->host throughput

#include <accessor.h>
#include <celerity.h>
#include <chrono>
#include <cstdint>
#include <iomanip>
#include <handler.h>
#include <iostream>
#include <queue.h>
#include <range_mapper.h>
#include <ranges.h>

#include "helpers.h"
//using namespace celerity;

constexpr size_t coarsening_fac = 1;

int main(int argc, char* argv[]) {
    const uint64_t data_size = (argc > 1) ? std::stoul(argv[1]) : 32*32*1024*1024; // elements

    std::cout << "Data size: " << data_size << " elements" << std::endl;

    Measurement timing_rw_kernel("read write");
    Measurement timing_r_kernel("read only");
    Measurement timing_first_kernel("first access (read only) (host to device)");
    Measurement timing_buffer_creation("buffer creation");
    Measurement timing_d2h("device to host");

    // Initialize runtime
    celerity::queue queue;

    timing_buffer_creation.measureStart();
    celerity::buffer<std::uint32_t, 1> buf(NULL, celerity::range<1>(data_size));
    queue.submit([&](celerity::handler &cgh) {
	
        celerity::accessor acc{buf, cgh, celerity::access::all{},
			celerity::write_only_host_task, celerity::no_init};
        cgh.host_task(celerity::once, [=]{
            for (uint64_t i = 0; i < data_size; i++) {
                acc[i] = 1;
            }
        });
    });

    queue.wait(celerity::experimental::barrier);
    timing_buffer_creation.measureEnd();

    struct coarsening {
		celerity::subrange<1> operator()(const celerity::chunk<1>& chnk) const {
			return celerity::subrange<1>(chnk.offset*coarsening_fac, chnk.range*coarsening_fac);
		}
	};

    // Kernel execution benchmark

    queue.wait(celerity::experimental::barrier);
    timing_first_kernel.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::one_to_one{}, celerity::read_write);

        cgh.parallel_for(celerity::range<1>(data_size),[=](celerity::item<1> item) {
            if(acc[item] == 3){
                acc[item] = 2;
            };
        });
    });

    queue.wait(celerity::experimental::barrier);
    timing_first_kernel.measureEnd();


    timing_r_kernel.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, coarsening{}, celerity::read_write);

        cgh.parallel_for(celerity::range<1>(data_size/coarsening_fac),[=](celerity::item<1> item) {
            size_t base_id = item.get_id(0) * coarsening_fac;
            for(size_t i = 0; i < coarsening_fac; i++){
                if(acc[base_id + i] == 4) {
                    acc[base_id + i] = 0;
                };
            }
        });
    });

    queue.wait(celerity::experimental::barrier);
    timing_r_kernel.measureEnd();

    timing_rw_kernel.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::one_to_one{}, celerity::read_write);

        cgh.parallel_for(celerity::range<1>(data_size),[=](celerity::item<1> item) {
            acc[item] = acc[item] + 1;
        });
    });

    queue.wait(celerity::experimental::barrier);
    timing_rw_kernel.measureEnd();

    bool correct = false;
    timing_d2h.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::all{}, celerity::read_only_host_task);
        cgh.host_task(celerity::once, [=, &correct] { correct = acc[0] == 2 && acc[data_size - 1] == 2; });
    });

    queue.wait(celerity::experimental::barrier);
    timing_d2h.measureEnd();

    std::cout << std::setprecision(std::numeric_limits<double>::max_digits10)<< std::fixed;
    std::cout << "\n=== Benchmark Results ===\n";
    uint64_t bytes = (uint64_t) data_size * sizeof(uint32_t);
    
    std::cout << "Data Size: " << (double) bytes / (1024*1024*1024) << "GiB\n";
    timing_buffer_creation.printTimeWithGBpS(bytes);
    timing_first_kernel.printTimeWithGBpS(bytes);
    timing_r_kernel.printTimeWithGBpS(bytes);
    timing_rw_kernel.printTimeWithGBpS(bytes);
    timing_d2h.printTimeWithGBpS(bytes);
    std::cout << "Check: " << (correct ? "ok" : "FAILED") << "\n";

    return 0;
}
