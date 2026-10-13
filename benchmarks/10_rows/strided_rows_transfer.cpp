// strided_rows_transfer: strided_transfer (src/strided_transfer.cpp) with wider rows. The kernels and host accesses touch the first W
// columns of an N x M buffer of 4-byte values: per row S = 4 * W useful bytes, then 4 * (M - W) bytes not accessed, i.e. a row pitch of
// 4 * M bytes in the host allocation. On the device only the N x W block is allocated (contiguous), as in strided_transfer.
// W = M copies whole rows: a contiguous copy, which takes Celerity's regular path (not copylib) unless CELERITY_COPYLIB_ROUTE=all.
// Kernels are launched as 1D ranges over the N * W elements (a 2D range of that size exceeds DPC++'s HIP grid limits).
// Output as in strided_transfer, with all GB/s except buffer creation computed on the N * W * 4 useful bytes.

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
    const uint64_t N = (argc > 1) ? std::stoul(argv[1]) : 1024; // rows
    const uint64_t M = (argc > 2) ? std::stoul(argv[2]) : 64;   // 4-byte values per row (row pitch)
    const uint64_t W = (argc > 3) ? std::stoul(argv[3]) : 8;    // 4-byte values per row that are copied
    if (W < 1 || W > M) {
        std::cerr << "need 1 <= W <= M\n";
        return 1;
    }

    std::cout << "Data size: " << N * M << " elements, rows of " << W * 4 << " useful bytes with a pitch of " << M * 4 << " bytes" << std::endl;

    Measurement timing_rw_kernel("read write");
    Measurement timing_r_kernel("read only");
    Measurement timing_first_kernel("first access (read only) (host to device)");
    Measurement timing_buffer_creation("buffer creation");
    Measurement timing_d2h("device to host");

    celerity::queue queue;
    const auto block = celerity::access::fixed<2>(celerity::subrange<2>({0, 0}, {N, W}));

    timing_buffer_creation.measureStart();
    celerity::buffer<std::uint32_t, 2> buf(NULL, celerity::range<2>(N, M));
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc{buf, cgh, celerity::access::all{}, celerity::write_only_host_task, celerity::no_init};
        cgh.host_task(celerity::once, [=] {
            for (uint64_t i = 0; i < N; i++) {
                for (uint64_t j = 0; j < M; j++) {
                    acc[i][j] = 1;
                }
            }
        });
    });
    queue.wait(celerity::experimental::barrier);
    timing_buffer_creation.measureEnd();

    // each kernel: if value == from, set it to to (as strided_transfer's kernels), over the N x W block, launched as 1D
    const auto block_kernel = [&](uint32_t from, uint32_t to) {
        queue.submit([&](celerity::handler& cgh) {
            celerity::accessor acc(buf, cgh, block, celerity::read_write);
            cgh.parallel_for(celerity::range<1>(N * W), [=](celerity::item<1> item) {
                const celerity::id<2> idx(item[0] / W, item[0] % W);
                if (acc[idx] == from) {
                    acc[idx] = to;
                }
            });
        });
        queue.wait(celerity::experimental::barrier);
    };

    queue.wait(celerity::experimental::barrier);
    timing_first_kernel.measureStart();
    block_kernel(3, 2);
    timing_first_kernel.measureEnd();

    timing_r_kernel.measureStart();
    block_kernel(3, 2);
    timing_r_kernel.measureEnd();

    timing_rw_kernel.measureStart();
    block_kernel(1, 2);
    timing_rw_kernel.measureEnd();

    bool correct = false;
    timing_d2h.measureStart();
    queue.submit([&](celerity::handler& cgh) {
        celerity::accessor acc(buf, cgh, block, celerity::read_only_host_task);
        cgh.host_task(celerity::once, [=, &correct] { correct = acc[0][0] == 2 && acc[N - 1][W - 1] == 2 && acc[N / 2][W / 2] == 2; });
    });
    queue.wait(celerity::experimental::barrier);
    timing_d2h.measureEnd();

    std::cout << "\n=== Benchmark Results ===\n";
    const uint64_t bytes = N * W * sizeof(uint32_t);
    std::cout << std::setprecision(std::numeric_limits<double>::max_digits10) << std::fixed;
    std::cout << "Data Size: " << (double)N * M * sizeof(uint32_t) / (1024 * 1024 * 1024) << "GiB\n";
    std::cout << "Worked on Data Size: " << (double)bytes / (1024 * 1024 * 1024) << "GiB\n";
    timing_buffer_creation.printTimeWithGBpS(N * M * sizeof(uint32_t));
    timing_first_kernel.printTimeWithGBpS(bytes);
    timing_r_kernel.printTimeWithGBpS(bytes);
    timing_rw_kernel.printTimeWithGBpS(bytes);
    timing_d2h.printTimeWithGBpS(bytes);
    std::cout << "Check: " << (correct ? "ok" : "FAILED") << "\n";
    return 0;
}
