# Task / launch overhead benchmark (idea 2)

One tiny kernel (`p[i] += 1` on ints) submitted N times, in six implementations with identical protocol:
plain SYCL on AdaptiveCpp, plain SYCL on DPC++, Celerity with copylib, Celerity without copylib, OpenCL, direct HIP.
It measures how much time the programming model adds per task, not kernel speed (use small `elems`).

```
overhead_<impl> <tasks> <elems> <buffers> [reps=7] [latency_samples=200]      (celerity: [strided=0|1] as 6th argument)
```

- Task i increments buffer `i % buffers`. `buffers=1` is a dependency chain, `buffers=64` gives mostly independent tasks.
- Per repetition: time to submit all N tasks, then time until everything completed. Medians over `reps`.
- Warmup (64 tasks + wait) runs first, so allocation, kernel loading and JIT are not measured.

Output (all programs):
```
Config: impl=... tasks=... elems=... buffers=... reps=... strided=...
Submit: x us/task     host time to enqueue all tasks / N (how fast the host side issues work)
Total: x us/task      enqueue + completion / N (throughput-bound per task cost)
Drain: x us           time from the last submission until completion (how far execution lagged behind submission)
Latency: x us         median of single "submit one task, wait" round trips
Check: ok|FAILED      every element equals the number of increments its buffer received
```

## Implementation notes (what is and is not comparable)
- SYCL / HIP / OpenCL use one in-order queue/stream and device memory: a task is one kernel launch, no dependency tracking by the library.
  Celerity does task graph, command graph and instruction graph generation per task plus `queue::wait()` for waiting, so
  Total minus the plain-SYCL Total (same SYCL implementation) is the Celerity overhead per task.
- Celerity runs on one process, no MPI. Compare Celerity-on-acpp with plain acpp and Celerity-on-dpcpp with plain dpcpp.
- With `strided=1` (Celerity only) each task is a 2D kernel (elems x 16 items) plus a host task reading column 0, forcing a strided
  device-to-host copy per task. This is the only mode where copylib vs no-copylib can differ, because copylib routes only strided copies;
  its extra cost/benefit shows up in Total and Latency. For `strided=0` both Celerity builds should be identical apart from executor startup.
- OpenCL picks platform/device via `OPENCL_PLATFORM`, `OPENCL_DEVICE` (indices); the GPU devices only, unless `OPENCL_ANY_DEVICE=1`.
- Process startup, buffer creation and the first-kernel load are not part of any metric.

## Build and run
```
GPU_ARCH=gfx1200 ./build.sh acpp dpcpp hip opencl
CELERITY_IMPL=acpp ./build.sh celerity-copylib celerity-nocopylib      # then again with CELERITY_IMPL=dpcpp0326
./run.sh results.csv                         # sweep: tasks 100 1000 10000 x elems 1 1024 1048576 x buffers 1 64 (override via TASKS/ELEMS/BUFFERS/REPS/STRIDED)
```
`build.sh` defaults to the `~/finalizing-work` layout of gpuc4/ifi/LUMI (see header of the script); binaries land in `build/`.
Binary names: `overhead_{acpp,dpcpp,hip,opencl}`, `overhead_celerity_{acpp,dpcpp0326}_{copylib,nocopylib}`.
The CSV has one row per data point: `binary,tasks,elems,buffers,strided,submit_us_per_task,total_us_per_task,drain_us,latency_us,check`.
