// strided_both_transfer: strided_transfer (src/strided_transfer.cpp) with the column strided on BOTH sides. Before the timed phases, a
// kernel touches the whole N x M buffer, so the device allocation also holds full rows (pitch M * 4 bytes), and a host task rewrites
// column 0, so the host holds its newest version. The timed copies of column 0 then go from the strided host allocation into the
// strided device allocation (first access) and back (device to host). Everything else, including the output, is as in strided_transfer.

#include <accessor.h>
#include <celerity.h>
#include <chrono>
#include <cstdint>
#include <handler.h>
#include <iomanip>
#include <iostream>
#include <limits>
#include <queue.h>
#include <range_mapper.h>
#include <ranges.h>

#include "helpers.h"
//using namespace celerity;

constexpr size_t coarsening_fac = 1;

int main(int argc, char* argv[]) {
    const uint64_t N = (argc > 1) ? std::stoul(argv[1]) : 1024; // elements
    const uint64_t M = (argc > 2) ? std::stoul(argv[2]) : 32*32*1024; // elements

    std::cout << "Data size: " << N * M << " elements" << std::endl;

    Measurement timing_rw_kernel("read write");
    Measurement timing_r_kernel("read only");
    Measurement timing_first_kernel("first access (read only) (host to device)");
    Measurement timing_buffer_creation("buffer creation");
    Measurement timing_d2h("device to host");

    // Initialize runtime
    celerity::queue queue;

    timing_buffer_creation.measureStart();
    celerity::buffer<std::uint32_t, 2> buf(NULL, celerity::range<2>(N,M));
    queue.submit([&](celerity::handler &cgh) {
	
        celerity::accessor acc{buf, cgh, celerity::access::all{},
			celerity::write_only_host_task, celerity::no_init};
        cgh.host_task(celerity::once, [=]{
            for (uint64_t i = 0; i < N; i++) {
                for (uint64_t j = 0; j < M; j++) {
                    acc[i][j] = 1;
                }
            }
        });
    });

    queue.wait(celerity::experimental::barrier);
    timing_buffer_creation.measureEnd();

    // untimed: allocate the whole N x M buffer on the device (strided device side), then make the host the newest holder of column 0.
    // A 1D launch: DPC++ maps a 2D range (N, M) with N * M >= 2^28 to a HIP grid beyond its limits (hipErrorInvalidValue).
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc{buf, cgh, celerity::access::all{}, celerity::write_only, celerity::no_init};
        cgh.parallel_for(celerity::range<1>(N * M), [=](celerity::item<1> item) { acc[celerity::id<2>(item[0] / M, item[0] % M)] = 1; });
    });
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::fixed<2>(celerity::subrange<2>({0, 0}, {N, 1})), celerity::write_only_host_task,
            celerity::no_init);
        cgh.host_task(celerity::once, [=] {
            for (uint64_t i = 0; i < N; i++) {
                acc[i][0] = 1;
            }
        });
    });
    queue.wait(celerity::experimental::barrier);

    // Kernel execution benchmark

    queue.wait(celerity::experimental::barrier);
    timing_first_kernel.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::one_to_one{}, celerity::read_write);

        cgh.parallel_for(celerity::range<2>(N, 1), [=](celerity::item<2> item) {
            if(acc[item] == 3){
                acc[item] = 2;
            };
        });
    });

    queue.wait(celerity::experimental::barrier);
    timing_first_kernel.measureEnd();


    timing_r_kernel.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::one_to_one{}, celerity::read_write);

        cgh.parallel_for(celerity::range<2>(N,1), [=](celerity::item<2> item) {
            if(acc[item] == 3){
                acc[item] = 2;
            };
        });
    });

    queue.wait(celerity::experimental::barrier);
    timing_r_kernel.measureEnd();

    timing_rw_kernel.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::one_to_one{}, celerity::read_write);

        cgh.parallel_for(celerity::range<2>(N, 1), [=](celerity::item<2> item) {
            if(acc[item] == 1){
                acc[item] = 2;
            };
        });
    });

    queue.wait(celerity::experimental::barrier);
    timing_rw_kernel.measureEnd();

    bool correct = false;
    timing_d2h.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::fixed<2>(celerity::subrange<2>({0, 0}, {N, 1})), celerity::read_only_host_task);
        cgh.host_task(celerity::once, [=, &correct] { correct = acc[0][0] == 2 && acc[N - 1][0] == 2; });
    });

    queue.wait(celerity::experimental::barrier);
    timing_d2h.measureEnd();

    std::cout << "\n=== Benchmark Results ===\n";
    uint64_t bytes = N * sizeof(uint32_t);
    
    std::cout << std::setprecision(std::numeric_limits<double>::max_digits10)<< std::fixed;
    std::cout << "Data Size: " << (double) M * bytes / (1024*1024*1024) << "GiB\n";
    std::cout << "Worked on Data Size: " << (double) bytes / (1024*1024*1024) << "GiB\n";
    timing_buffer_creation.printTimeWithGBpS(M * bytes);
    timing_first_kernel.printTimeWithGBpS(bytes);
    timing_r_kernel.printTimeWithGBpS(bytes);
    timing_rw_kernel.printTimeWithGBpS(bytes);
    timing_d2h.printTimeWithGBpS(bytes);
    std::cout << "Check: " << (correct ? "ok" : "FAILED") << "\n";

    return 0;
}
