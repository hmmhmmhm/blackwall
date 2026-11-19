# Host Bottleneck in Original ARM Execution: PC Observation Hooks

Follow-up bw399: [selective suspension of owned callbacks](../research/scoped-observer-suspension.md) was implemented opt-in, and state/performance were compared across five original-run pairs. Below is the bottleneck investigation before that change.

bw398. Managed-code stacks were collected during actual busy polling in stock 2.4, and observation-point hit increases were compared in a separate run. **Most observed time in this segment concentrated in PC breakpoint removal/re-registration paths.** No evidence justified changing memory-protection policy. No performance improvement was applied or speedup claimed in this work. Overall 7/16 (43.8%) remains unchanged.

## Collection method

Following official Microsoft [dotnet-trace documentation](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/dotnet-trace), EventPipe managed-code thread-time was collected for 15 seconds. Tool version was `10.0.750501`, and the official Linux ARM64 download was SHA-256 pinned. The .NET 8.0.34 runtime for the tool was checked against SHA-512 in official release metadata and installed only in a private work folder. Existing Renode image and original main were unchanged.

The target used pinned Renode image `e840c2b9…` and existing frozen-core fault input. PID and virtual time were recorded after ten actual busy polls, then collection began. The container containing target/profiler used CPU 1, memory 1 GiB, network none, and dropped capabilities. Because of sampler and extra memory, this run is **excluded from performance comparisons**.

The native process terminated on its own; the trace was 25,299,446 bytes. The full collection run recorded busy 855, request 2/trigger 1, calculations 0, and guard 0, ending at the host limit. Original timeout return and normal boot remain unverified.

## Actual stack results

The all-thread aggregate gives waiting threads substantial weight, so CPU execution `Thread (32)` was isolated. Original nettrace and converted Speedscope evented stack intervals were retained.

| CPU execution thread path | Inclusive thread-time share |
| --- | ---: |
| `TlibAddBreakpoint` | 43.59% |
| `TlibRemoveBreakpoint` | 43.56% |
| Combined two native interop paths | 87.14% |

This is **sample-based thread observation time** from one profile, not CPU cycles, hardware FPS, an improvement factor, or a representative repeated-measurement value. Native internal frames are opaque. Interpret it as time observed in native calls connected to managed `HookDescriptorBase.Reactivate/DeactivateHooks`. `BlackwallMemoryPolicy` frames did not appear in these CPU-thread samples, but that does not prove zero cost.

## Which observation points?

A subsequent original run retained the model, guest code, and existing hooks, dumping only `observer.Points` hit counts before and after a dedicated segment. Specific labels were not inferred from CPU stacks alone; actual counters were checked.

| Observation label | Original PC | Increase during segment |
| --- | --- | ---: |
| `iom7-address` | `0x5821d4` | 1,512 |
| `iom7-fifo` | `0x582354` | 1,046 |
| `iom7-command` | `0x58236c` | 1,046 |

Other general observation points increased by zero. The iom7 label is historical; these addresses are shared HAL paths also called by this IMU/IOM4 transaction. The three PC observation hooks continued to be called repeatedly even after obtaining the initial SRAM snapshot.

`BlackwallExecutionObserver.AddPoint` registers a hook at each PC to record host hits/events/snapshots. It does not substitute firmware results or branches. The installed engine's `RemoveHook(UInt64, CpuAddressHook)` was confirmed in a firmware-free API check. `RemoveAllHooks` or removal of all hooks at an address could affect other diagnostics and safety mechanisms and must not be used for the next improvement.

## Next improvement and assessment criteria

Consider an opt-in observation mode that **selectively removes only the three callbacks owned by that observer** at a legitimate pause after the initial prefix and ATT input handling. Preserve memory/MMU/block protection, peripheral strictness, IRQ, firmware timeout, and original branches/returns/TCB/SP. First test by actual execution whether another owner's hook at a shared callback address remains alive, and check unknown labels and idempotence.

Then compare full CPU/SRAM and device state between existing observation and new mode using the same board, input, and virtual boundary. The existing contract that hook changes are execution configuration remains. If IT/block boundaries or timing create differences, do not hide them or exclude arbitrary addresses. Report an adopted speed improvement only after alternating repeated runs without a profiler and checking total execution cost as well. No replacement implementation was adopted in this investigation.

## Failure and verification history

The first collection attempt failed at the marker's `System.Diagnostics.Process` import and obtained no original trace. After confirming `Environment.ProcessId` with a small firmware-free Renode test, a new output was used for the retry. The first result was not overwritten.

The first trace report failed while attempting to create an .etlx cache beside a read-only capture. The source capture's permissions were not loosened; a separate analysis copy with identical SHA was made to generate the report. Analysis cache and original trace are distinguished.

Private evidence: `execution-bottleneck-profile-01/{tool-download.json,runtime-download.json,attempt-02,trace-analysis,cpu-thread-inclusive.json,point-attribution.json,manifest.json}`, `gaf-host-profile-native-02/stock24`, `gaf-point-counters-native-01/stock24`. The failed collection is preserved in `gaf-host-profile-native-01/stock24`. New original runs were one preliminary, one successful stack collection, and one counter attribution; tool API checks used zero ARM executions.

The existing 16 acceptance/status/evidence criteria and API 3/6 were retained. No physical access, Astra/subagent, or external publication occurred.
