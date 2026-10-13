// Celerity throughput benchmark: copies that are contiguous on the host and strided on the device (the counterpart of strided_transfer, where the
// host side is strided and the device side contiguous).
// The device allocation is N x M elements (a kernel initializes the whole buffer first), the host only ever touches column 0, so its allocation is
// the N x 1 box and contiguous. Host to device then copies a contiguous host box into a strided device region, device to host the reverse.
// Output format as strided_transfer, so the same wrapper metrics apply. Usage: device_strided_transfer N M   (N rows, M elements per row on the device)

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

int main(int argc, char* argv[]) {
    const uint64_t N = (argc > 1) ? std::stoul(argv[1]) : 1024; // elements
    const uint64_t M = (argc > 2) ? std::stoul(argv[2]) : 32*32*1024; // elements

    std::cout << "Data size: " << N * M << " elements" << std::endl;

    Measurement timing_rw_kernel("read write");
    Measurement timing_r_kernel("read only");
    Measurement timing_first_kernel("first access (read only) (host to device)");
    Measurement timing_buffer_creation("buffer creation");
    Measurement timing_d2h("device to host");

    celerity::queue queue;

    timing_buffer_creation.measureStart();
    celerity::buffer<std::uint32_t, 2> buf(celerity::range<2>(N, M));
    // the device allocates and initializes the whole N x M buffer
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc{buf, cgh, celerity::access::one_to_one{}, celerity::write_only, celerity::no_init};
        cgh.parallel_for(celerity::range<2>(N, M), [=](celerity::item<2> item) { acc[item] = 0; });
    });
    // the host writes column 0 only: its allocation is the contiguous N x 1 box
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc{buf, cgh, celerity::access::fixed<2>(celerity::subrange<2>({0, 0}, {N, 1})), celerity::write_only_host_task, celerity::no_init};
        cgh.host_task(celerity::once, [=] {
            for(uint64_t i = 0; i < N; i++) { acc[i][0] = 1; }
        });
    });
    queue.wait(celerity::experimental::barrier);
    timing_buffer_creation.measureEnd();

    // host (contiguous N x 1) to device (strided N x 1 inside N x M)
    queue.wait(celerity::experimental::barrier);
    timing_first_kernel.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::fixed<2>(celerity::subrange<2>({0, 0}, {N, 1})), celerity::read_write);
        cgh.parallel_for(celerity::range<2>(N, 1), [=](celerity::item<2> item) {
            if(acc[item] == 3) { acc[item] = 2; }
        });
    });
    queue.wait(celerity::experimental::barrier);
    timing_first_kernel.measureEnd();

    timing_r_kernel.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::fixed<2>(celerity::subrange<2>({0, 0}, {N, 1})), celerity::read_write);
        cgh.parallel_for(celerity::range<2>(N, 1), [=](celerity::item<2> item) {
            if(acc[item] == 3) { acc[item] = 2; }
        });
    });
    queue.wait(celerity::experimental::barrier);
    timing_r_kernel.measureEnd();

    timing_rw_kernel.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, celerity::access::fixed<2>(celerity::subrange<2>({0, 0}, {N, 1})), celerity::read_write);
        cgh.parallel_for(celerity::range<2>(N, 1), [=](celerity::item<2> item) {
            if(acc[item] == 1) { acc[item] = 2; }
        });
    });
    queue.wait(celerity::experimental::barrier);
    timing_rw_kernel.measureEnd();

    // device (strided) to host (contiguous N x 1)
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

    std::cout << std::setprecision(std::numeric_limits<double>::max_digits10) << std::fixed;
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
