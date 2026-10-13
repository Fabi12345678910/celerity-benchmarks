# Contiguous host<->device memcpy on AMD: HIP, OpenCL, AdaptiveCpp, DPC++, Celerity (native and copylib)

Source-only study (2026-10-07, nothing built or run for it; the measurements and rocprofv3 traces of this folder check it). References are
`repo:path:line` at: `clr` = ROCm/clr rocm-7.1.0, `clr644` = ROCm/clr rocm-6.4.4, `rocr` = ROCm/ROCR-Runtime rocm-7.1.0,
`hip` = ROCm/HIP rocm-7.1.0 (headers), `acpp` = AdaptiveCpp 9f842c70, `llvm` = intel/llvm b224a21db0fb (nightly-2026-03-26),
`cel` = Celerity 3dcopylib-bench 014e21a (the deployed 2dda28f only changes defaults on top).

## Verdict

The hypothesis ("all are pretty much hip memcpy with some data management around, perhaps OpenCL differs") is **largely confirmed for the
device-side mechanism, partly refuted for the host side.**

- **Confirmed:** every SYCL-based path (AdaptiveCpp USM, DPC++ USM, Celerity native, Celerity + copylib for contiguous copies) ends in exactly
  one `hipMemcpyAsync` per contiguous copy. In CLR, `hipMemcpy[Async]` and OpenCL `clEnqueue{Read,Write,Copy}Buffer` build the same ROCclr
  commands (`Write/Read/CopyMemoryCommand`), go through the same `roc::KernelBlitManager` / `DmaBlitManager` and end in the same
  `hsa_amd_memory_async_copy[_on_engine]` (SDMA), or in a ROCr blit kernel with `HSA_ENABLE_SDMA=0`. The copy kind (`hipMemcpyDefault` vs
  explicit H2D/D2H) does not matter: CLR classifies by pointer lookup.
- **What differs:**
  1. **Pinned vs pageable host memory** is by far the biggest effect, and it comes from the memory the program uses, not from the model.
     Pageable memory goes through CLR staging: CPU memcpy through a 4 x 1 MiB staging ring up to 1 MiB, on-the-fly pinning in 32 MiB chunks
     above. Pageable copies are effectively synchronous even when issued "async". Pinned memory (`hipHostMalloc` / `malloc_host` / Celerity)
     is copied directly by SDMA (a CLR blit kernel at <= 16 KiB). Celerity always copies from/to pinned memory.
  2. **OpenCL:** same engine, but no direct dispatch (a per-queue worker thread submits), no active wait (blocking calls sleep on a
     condition variable / interrupt signal), and `GPU_FORCE_BLIT_COPY_SIZE` = 0, so small copies take SDMA instead of HIP's <= 16 KiB blit
     kernel. That costs latency per call, not bandwidth.
  3. **Per-copy host bookkeeping:** AdaptiveCpp 2-3 `hipPointerGetAttributes` + 1 `hipEventRecord`; DPC++ `hipSetDevice` +
     `hipEventCreateWithFlags`/`Record`/`Destroy`; Celerity task/command/instruction graph generation, executor -> submitter thread hop with
     a `std::promise`, busy-polling executor. Data from a user host pointer costs Celerity an extra CPU memcpy into pinned memory, and
     `fence()` one back.

## 1. Plain HIP (CLR 7.1.0)

**Call chain.** `hipMemcpy` -> `hipMemcpy_common` (null stream) -> `ihipMemcpy(..., isHostAsync=false)` (`clr:hipamd/src/hip_memory.cpp:797,780-795`,
`hip_internal.hpp:689-690`); `hipMemcpyAsync` -> `hipMemcpyAsync_common` -> `ihipMemcpy(..., true)` (`hip_memory.cpp:1392-1405`);
`hipMemcpyHtoD/DtoH` the same (`:1562-1580`). `ihipGetMemcpyType` (`:501-528`) looks both pointers up in the global `amd::MemObjMap` (`:40-41`):
host pointer not found (pageable) -> `hipWriteBuffer` / `hipReadBuffer`; both found (`hipHostMalloc`'d or registered + device) -> `hipCopyBuffer`.
`kind` only matters for `hipMemcpyDeviceToDeviceNoCU`. `ihipMemcpyCommand` (`:531-623`) creates `WriteMemoryCommand` (`:552`) /
`ReadMemoryCommand` (`:565`) / `CopyMemoryCommand` (`:614`) with `CopyMetadata(isAsync, NONE)`, then `enqueue()` and, if not host-async,
`finishCommand` (`:691-696`). With direct dispatch (HIP default, `hip_context.cpp:44-54`) the command is submitted in the caller's thread
(`rocclr/platform/command.cpp:361-391`). Device layer: `VirtualGPU::submitWriteMemory` -> `blitMgr().writeBuffer`
(`rocclr/device/rocm/rocvirtual.cpp:2170-2219`), `submitReadMemory` -> `readBuffer` (`:2066-2111`), `submitCopyMemory` -> `copyBuffer`
(`:2422-2440`, `:2329-2381`).

**Pageable host memory.**
- `<= sdmaCopyThreshold_` (`GPU_FORCE_BLIT_COPY_SIZE`, default 16 KiB; `rocsettings.cpp:63`, `utils/flags.hpp:189`): shader copy through the
  staging buffer. H2D: CPU memcpy into staging (`rocblit.cpp:1889`), blit kernel on the stream's own AQL queue (`:1903-1905`,
  `shaderCopyBuffer` `:2192-2247`). D2H: blit into staging, `WaitCurrent`, CPU memcpy (`:1756-1769`).
- Larger: `DmaBlitManager::writeBuffer/readBuffer` -> `hsaCopyStagedOrPinned` (`rocblit.cpp:135-158`, `53-77`, `691-781`).
  - `<= pinnedMinXferSize_` (1 MiB on ROCm, `rocsettings.cpp:60-61`): staging chunks of `stagedXferSize_` (1 MiB, `:54`) from a 4 x 1 MiB
    ring per queue (`rocvirtual.hpp:199`, `rocvirtual.cpp:1609`, `1817-1846`). H2D: CPU memcpy then `rocrCopyBuffer` (`rocblit.cpp:722-731`);
    D2H: `rocrCopyBuffer`, `WaitCurrent`, CPU memcpy (`:734-746`).
  - `> 1 MiB`: the user range is pinned on the fly in `GPU_PINNED_XFER_SIZE` chunks (32 MiB; `flags.hpp:81`, `rocsettings.cpp:59,111`) via
    `pinHostMemory` -> `amd::Buffer(CL_MEM_USE_HOST_PTR)` (HSA memory lock, cached by `findPinnedMem`; `rocblit.cpp:2640-2683`, decision
    `:643-675`); SDMA reads/writes the user pages directly; under HIP the runtime then waits and unpins (`:760-765`).
  - Before a pageable D2H the CPU waits for all prior work on the queue: `releaseGpuMemoryFence(hostToDev || !blocking_blit_)`
    (`rocblit.cpp:695`, `rocvirtual.cpp:1579-1593`), `blocking_blit_ = IS_HIP || !AMD_DIRECT_DISPATCH` (`rocsettings.cpp:98`).
  - Consequence: `hipMemcpyAsync` on pageable memory is only asynchronous for H2D <= 1 MiB (returns after the CPU staging memcpy); every D2H
    and every H2D > 1 MiB blocks the host.

**Pinned host memory (`hipHostMalloc`).** `ihipHostMalloc` (`hip_memory.cpp:371-427`) always sets `CL_MEM_SVM_FINE_GRAIN_BUFFER` (`:392`)
and, for flags 0 / Coherent / Mapped / NumaUser, `CL_MEM_SVM_ATOMICS` (`:403-408`): fine-grained coherent system pool; `NonCoherent` removes
it (`:414-416`). `hipHostMallocDefault == 0` (`hip:include/hip/hip_runtime_api.h:815`). Copy: `KernelBlitManager::copyBuffer`
(`rocblit.cpp:2252-2330`): blit kernel (zero-copy over the link) if `size <= 16 KiB` and no SDMA preference (`:2285-2292`), otherwise
`DmaBlitManager::copyBuffer` -> `hsaCopy` -> `rocrCopyBuffer` (`:2304`, `:218-233`, `:588-638`). No staging, no CPU memcpy; one CPU wait for
prior work only for a blocking D2H (`:629-635`).

**Engine.** `rocrCopyBuffer` (`rocblit.cpp:474-585`): engine type CPU->GPU `SdmaWrite`, GPU->CPU `SdmaRead` (`:493-500`), queries free /
recommended engines, calls `hsa_amd_memory_async_copy_on_engine(..., wait_events, completion_signal, engine)` (`:556-558`), falls back to
`hsa_amd_memory_async_copy` (`:570`); dependencies are HSA signals, not CPU waits. In ROCr, `HSA_ENABLE_SDMA` (`rocr:runtime/hsa-runtime/core/util/flag.h:89-90`)
decides whether the H2D/D2H blit objects are SDMA or a ROCr `BlitKernel` on an internal ROCr AQL queue (`core/runtime/amd_gpu_agent.cpp:797-845,874-876`);
`DmaCopyOnEngine` with SDMA disabled forces `BlitDevToDev` (`:1145-1152`). So with `HSA_ENABLE_SDMA=0` every SDMA-path copy becomes a ROCr
blit kernel on ROCr's internal queue (not the HIP stream's queue); CLR's own <= 16 KiB blit kernels are unaffected.

**Synchronisation.** Blocking `hipMemcpy`: the null stream first waits for all active blocking streams (`hip_device.cpp:45-55`), then
`finishCommand` waits for the HW event (`hip_memory.cpp:694-696`, `commandqueue.cpp:144-159`). HIP sets active wait (spinning) on all
devices (`hip_context.cpp:69-71`). Per copy: one `amd::Command`, the batch lock, one HSA completion signal from the queue's pool.

**ROCm 6.4.4 (LUMI):** same structure and defaults (`clr644:rocclr/device/rocm/rocsettings.cpp:58-68`, `rocblit.cpp:645-`, `:526`,
direct dispatch `hip_context.cpp:45-49`); the D2H fence uses `releaseGpuMemoryFence(hostToDev)` (`:649`), `writeBuffer` is not gated on
`blocking_blit_` (`:1795`). Not material for HIP.

## 2. OpenCL (same CLR)

`clEnqueueWriteBuffer` -> `WriteMemoryCommand` with `CopyMetadata(!blocking, SDMA)` (`clr:opencl/amdocl/cl_memobj.cpp:781-783`) ->
`enqueue`, `awaitCompletion` if blocking (`:796-799`); `clEnqueueReadBuffer` likewise (`:639-657`); `clEnqueueCopyBuffer` ->
`CopyMemoryCommand` (`:913`). Then the same `submitWriteMemory` / `submitReadMemory` / `copyMemory` -> `KernelBlitManager` ->
`hsaCopyStagedOrPinned` / `hsaCopy` -> `rocrCopyBuffer` as HIP: **same blit manager, same engine path.** OpenCL-specific:

1. **No direct dispatch:** `AMD_DIRECT_DISPATCH` defaults to false (`flags.hpp:184`), only the HIP init overrides it (`hip_context.cpp:54`).
   `HostQueue` starts a worker thread (`commandqueue.cpp:49-61`); `Command::enqueue` appends and flushes (`command.cpp:392-394`); the worker
   dequeues and submits (`commandqueue.cpp:230-300`): one thread hand-off per command.
2. **No active wait:** default false (`device.cpp:739`), so signals use interrupts (`rocvirtual.cpp:374-376`) and `awaitCompletion` sleeps on
   a condition variable (`command.cpp:246-257`); `clFinish` always waits on the CPU (`commandqueue.cpp:178-181`).
3. **`GPU_FORCE_BLIT_COPY_SIZE` = 0 for OpenCL** (`device.cpp:1209-1212`): even tiny copies take SDMA via `hsaCopyStagedOrPinned` (staging
   <= 1 MiB) instead of HIP's <= 16 KiB blit kernel; with `HSA_ENABLE_SDMA=0` a ROCr blit kernel.
4. The post-copy wait and unpin of `hsaCopyStagedOrPinned` is HIP-only (`rocblit.cpp:762`); OpenCL releases pinned chunks later.
5. Buffer objects: `CL_MEM_READ_WRITE` without host pointer -> `deviceLocalAlloc` (`rocmemory.cpp:947-948`), lazily on the first enqueue
   (`cl_memobj.cpp:791-794`). `USE_HOST_PTR` / `ALLOC_HOST_PTR` create a host-resident buffer (`rocmemory.cpp:1001-1030`); kernels then access
   system memory and reads/writes of such buffers become a CPU memcpy (`HostBlitManager`, `rocblit.cpp:57-62,139-145`).
6. Map/unmap of a device-local buffer maps an `ALLOC_HOST_PTR` (pinned) buffer (`rocmemory.cpp:81`), filled by `copyBuffer` (SDMA) or
   `readBuffer` (`rocvirtual.cpp:2759-2835`).

Note for `memcpy_opencl ... pinned`: its host pointer is a mapped `ALLOC_HOST_PTR` buffer. Whether CLR then finds it in `MemObjMap` (direct
SDMA) or stages it like pageable memory is one of the things the traces show.

## 3. AdaptiveCpp (HIP backend)

**USM `q.memcpy`, in-order queue:** `queue::memcpy` (`acpp:include/hipSYCL/sycl/queue.hpp:767-771`) -> `handler::memcpy`
(`handler.hpp:565-612`, pointer classification with 2-3 `hipPointerGetAttributes`, `usm_query.hpp:149-166`) -> `create_task` instant
submission (in-order bound queue, no buffer dependencies; `handler.hpp:1172-1218`, `queue.hpp:1179-1210`) -> `inorder_executor::submit_directly`
(`src/runtime/inorder_executor.cpp:91-186`) -> `hip_queue::submit_memcpy` -> **`hipMemcpyAsync(dst, src, n, H2D|D2H, stream)`**
(`src/runtime/hip/hip_queue.cpp:249-259,295-297`) on a per-queue `hipStreamNonBlocking` stream (`:174-179`). No staging, no kernel, no
`hipHostRegister`.
**Host memory:** `malloc_host` / `aligned_alloc_host` -> `hipHostMalloc(&ptr, bytes, hipHostMallocDefault)` (`src/runtime/hip/hip_allocator.cpp:48`):
fine-grained pinned; `malloc_device` -> `hipMalloc`; pageable pointers are passed through (CLR stages them).
**Per copy:** one `memcpy_operation`, `dag_node`, `hip_node_event`, one `hipEventRecord` (pooled events; `hip_queue.cpp:211-220`,
`hip_event_pool.cpp:21-34`); no `hipStreamWaitEvent`; `q.wait()` -> `hipStreamSynchronize` (`inorder_executor.cpp:202-204`).
`AdaptiveCpp_coarse_grained_events` removes the event record.
**Buffers:** `buffer(T*, range)` uses the user pointer as host backing (`buffer.hpp:497-519,1287-1314`); first device access: lazy `hipMalloc`,
`hipMemcpyAsync` H2D on a `multi_queue_executor` memcpy-lane stream (not the queue's stream), then `hipStreamWaitEvent` on the kernel stream
(`dag_direct_scheduler.cpp:79-108,124-198`; `hip_queue.cpp:282-297,433-447`); host accessor / destructor: D2H `hipMemcpyAsync` into the user
pointer + `hipEventSynchronize` (`accessor.hpp:1472-1542`, `buffer.hpp:209-267`). Pageable path in CLR.

## 4. DPC++ (SYCL RT + Unified Runtime HIP adapter)

**USM `q.memcpy`:** `queue::memcpy` (`llvm:sycl/source/queue.cpp:130-152`) -> `queue_impl::memcpy` -> `submitMemOpHelper`
(`sycl/source/detail/queue_impl.cpp:175-218,805-868`; scheduler bypass when dependencies allow, `scheduler.cpp:687-708`) ->
`MemoryManager::copy_usm` -> `urEnqueueUSMMemcpy(blocking=false)` (`memory_manager.cpp:848-870`) -> UR HIP
(`unified-runtime/source/adapters/hip/enqueue.cpp:1351-1382`): `hipSetDevice`, `getNextTransferStream()` (the single compute stream for in-order
queues, `common/cuda-hip/stream_queue.hpp:118-119,232-235`), a new `ur_event_handle_t_` (`hipEventCreateWithFlags(hipEventDisableTiming)`,
`event.cpp:16-34`), **`hipMemcpyAsync(dst, src, n, hipMemcpyDefault, stream)`** (`enqueue.cpp:1367-1368`), `hipEventRecord`. The event is
created even for in-order queues; only `ext::oneapi::experimental::memcpy` avoids it (`queue_impl.cpp:825-862`, `enqueue_functions.cpp:16-22`).
**Host memory:** `malloc_host` -> `urUSMHostAlloc` -> `hipHostMalloc(ptr, size)` (`hip/usm.cpp:173`, default flags -> fine-grained pinned);
device `hipMalloc` (`usm.cpp:63-65`); `urUSMImportExp` is a no-op (`usm.cpp:273-282`), pageable is passed to CLR.
**Buffers:** a writable aligned host pointer is used directly (`detail/sycl_mem_obj_t.hpp:178-205`); on a discrete GPU first access ->
`MemCpyCommand` -> `copyH2D` -> `urEnqueueMemBufferWrite` -> `hipMemcpyHtoDAsync` (lazy `hipMalloc`; `memory_manager.cpp:475-526`,
`enqueue.cpp:151-192`, `memory.cpp:437-461`), always the whole buffer (`graph_builder.cpp:390-399`); host accessor / destruction ->
`hipMemcpyDtoHAsync` into the user pointer + `hipEventSynchronize` (`sycl_mem_obj_t.cpp:125-147`, `enqueue.cpp:194-248`).

## 5. Celerity (3dcopylib-bench)

**Allocation:** host `sycl::aligned_alloc_host` (`cel:src/backend/sycl_backend.cc:317-325`) = `hipHostMalloc(Default)` on both SYCLs
(fine-grained pinned); device `sycl::aligned_alloc_device` (`:327-338`). Allocations, queues and the host context use different
`sycl::context`s (`:200,213,258`); irrelevant for CLR, which finds pinned pointers in the global `MemObjMap`.
**Native contiguous copy:** IDAG `copy_instruction` (`src/instruction_graph_generator.cc:1427`) -> out-of-order engine assigns
`target::device_queue` and an in-order lane (`src/out_of_order_engine.cc:204-249,288-302`) -> `live_executor::issue_async` ->
`enqueue_device_copy` (`live_executor.cc:770-795`) -> per-device submitter thread (`sycl_backend.cc:415-434`) -> `nd_copy_device_generic`:
both sides linearised -> **exactly one `queue.memcpy`** (`src/backend/sycl_generic_backend.cc:46-52`), then section 3 or 4 down to one
`hipMemcpyAsync` on pinned memory (CLR `hipCopyBuffer` -> SDMA, blit <= 16 KiB). Strided boxes give one memcpy per contiguous chunk
(`sycl_generic_backend.cc:22-36`, `include/nd_memory.h:67-118`).
**gpu3dcopylib:** vendored in-tree (`vendor/gpu3dcopylib-bench`, FetchContent from a local URL, `CMakeLists.txt:217-225`). Routes only
strided copies (all with `CELERITY_COPYLIB_ROUTE=all`; off with `CELERITY_COPYLIB=off`; `out_of_order_engine.cc:294-300`), so **a contiguous
copy is identical to native.** Routed copies are SYCL only (no direct HIP/HSA): CPU row packing into pinned staging or a device pack kernel,
then `queue.copy` per contiguous chunk on worker threads/queues with a blocking wait per chunk (`vendor/gpu3dcopylib-bench/src/backend.cpp:184-248,447-463,529-531,608-641`;
`core.cpp:109-190`). Unless `CELERITY_COPYLIB=off`, `init()` allocates device and pinned staging plus worker queues/threads per device
(`sycl_backend.cc:296-303`).
**Extra per-copy work:** a user host pointer is memory 0, not a copy peer of device memory (`sycl_backend.cc:232-241`), so the first device
read costs a pinned staging alloc instruction, a **CPU `std::memcpy` user -> pinned** on a host thread and the H2D `queue.memcpy`
(`instruction_graph_generator.cc:1252-1258,1353-1384`); `fence()` costs a D2H into pinned memory plus a **CPU memcpy pinned -> user**
(`:2232-2238`, `include/fence.h:96`). Host tasks access the pinned allocation directly (`live_executor.cc:920-928`). No write-back on
buffer destruction (`buffer.h:118-124`). Bookkeeping: task -> `execution_command` -> `copy_instruction` (+ alloc / horizon instructions),
`double_buffered_queue` (mutex + cv) to the executor, `std::function` + `std::promise` hop to the submitter thread (`thread_queue.h:50-58`),
the SYCL costs of section 3/4; completion by busy polling `get_info<command_execution_status>` while work is pending
(`live_executor.cc:421-473`, `sycl_backend.cc:44-61`); on AdaptiveCpp `dag().flush_async()` after each submit (`sycl_backend.cc:73-87`).

## 6. Summary

All rows end in the same ROCclr/ROCr engine: SDMA via `hsa_amd_memory_async_copy_on_engine`, or a ROCr blit kernel with `HSA_ENABLE_SDMA=0`;
HIP and the SYCL-based paths use a CLR blit kernel at <= 16 KiB.

| Model | H2D call | D2H call | Host memory | Engine | Extra per-copy work | Expected vs plain HIP |
|---|---|---|---|---|---|---|
| HIP | `hipMemcpy[Async]` -> `Write`/`CopyMemoryCommand` | `hipMemcpy[Async]` -> `Read`/`CopyMemoryCommand` | `hipHostMalloc` = fine-grained pinned | SDMA > 16 KiB, CLR blit <= 16 KiB; pageable: staging <= 1 MiB, pinning in 32 MiB chunks above | pageable: CPU staging memcpy, CPU wait before D2H, wait/unpin after | baseline |
| OpenCL | `clEnqueueWriteBuffer` -> `WriteMemoryCommand` (SDMA preference) | `clEnqueueReadBuffer` -> `ReadMemoryCommand` | device-local `cl_mem` (lazy) | same blit manager; SDMA even for tiny copies | worker-thread hand-off per command, interrupt / cv wait | same bandwidth, higher latency per call |
| AdaptiveCpp USM | `q.memcpy` -> `hipMemcpyAsync(H2D)` | `hipMemcpyAsync(D2H)` | `hipHostMalloc(Default)`; pageable passed through | as HIP | 2-3 `hipPointerGetAttributes`, `hipEventRecord`, `dag_node` | ~HIP + a few us host |
| AdaptiveCpp buffer | DAG -> `hipMemcpyAsync` on a memcpy-lane stream | same + `hipEventSynchronize` | user pointer (pageable) | as HIP pageable | DAG, `hipStreamWaitEvent`, lazy `hipMalloc` | pageable cost + DAG latency |
| DPC++ USM | `urEnqueueUSMMemcpy` -> `hipMemcpyAsync(Default)` | same | `hipHostMalloc`; pageable passed through | as HIP | `hipSetDevice`, `hipEventCreate/Record/Destroy`, queue mutex | ~HIP + a few us host |
| DPC++ buffer | `urEnqueueMemBufferWrite` -> `hipMemcpyHtoDAsync` | `hipMemcpyDtoHAsync` | user pointer (pageable) | as HIP pageable | scheduler graph, events, whole-buffer copies, host waits | pageable cost + scheduler latency |
| Celerity native | `copy_instruction` -> submitter thread -> one `queue.memcpy` -> `hipMemcpyAsync` | same | pinned (`aligned_alloc_host`) | SDMA on pinned memory | TDAG/CDAG/IDAG, thread hops, busy polling; user-pointer data adds a CPU memcpy each way | device side like pinned HIP; extra host latency per copy |
| Celerity + copylib | contiguous: identical to native | same | pinned staging | as above | (strided only: packing, per-chunk wait) | contiguous: none (start-up only) |

## Not verified from source

Runtime behaviour (checked by the traces of `trace.sh`), whether the deployed CLR has direct dispatch on (standard ROCm build: yes), SDMA
engine availability and ROCr `BlitKernel` details on gfx1200 / gfx1151 / gfx90a, and whether the DPC++ nightly was built with XPTI.

## Note on the measurements (2026-10-07)

Only the per-copy overhead at 4 B is the target. The LUMI run also covered 64 B .. 1 GiB; there Celerity's rates above a few MiB are not
comparable with the plain programs, because the one-item kernel lets Celerity copy only what is accessed rather than the whole buffer
(41 GB/s with SDMA off vs 25 GB/s for plain HIP, which is unaffected by NUMA binding: `job_lumi_numa.sbatch`).
