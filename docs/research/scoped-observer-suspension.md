# Selectively Suspending PC Observation After Startup

bw399. An opt-in mode was added to selectively suspend three shared IOM diagnostic hooks identified as a real bottleneck after startup and ATT input handling. **In a fixed 500 ms scenario preserving original ARM, board, and protections, median execution-segment time changed from 17.82 s to 1.77 s; total recorded execution including initialization and capture changed from 61.12 s to 45.94 s.** Default observation remains unchanged.

## Change and ownership

`BlackwallExecutionObserver` retains the `CpuAddressHook` delegates it registered and `SuspendPoint(label)` removes only those callbacks. It does not touch other owners' hooks. Repeated suspension returns false; empty, null, and unregistered labels are rejected. Hit counts, event history, and the first SRAM snapshot are preserved. The caller uses it while the machine is paused.

`probe_gaf_frozen_core.py --suspend-startup-observer` suspends only the `iom7-address/fifo/command` callbacks at a pause after the existing prefix and ATT processing complete without errors or guard failures. The labels are historical; these are shared HAL addresses also called for IMU/IOM4 transactions. Changes are limited to the observer namespace and explicit execution configuration.

The default path uses the existing pinned observer. There is no `RemoveAllHooks`, removal of all hooks at an address, disabling of memory/MMU/block protection, shortening of firmware loops, or modification of original branch/R0/TCB/SP. Do not extend this validation to other cases or every firmware ABI. This original integration comparison uses stock 2.4.

## Actual ARM ownership test

First, RED was confirmed on the old source without the API. A new actual M55 unit execution installed two observers and a separate pause callback at the same PC. After the first phase, only one owner's loop observation was suspended, and execution resumed without resetting CPU PC.

- The suspended owner's loop hits remained at 3; the other owner's increased from 3 to 6.
- The separate pause callback ran twice, guest phase progressed from 1 to 2, and result 42 was retained.
- Fifteen checks passed, including preservation of snapshots/event history and memory neighbors, idempotence, and rejection of an unregistered label.
- Existing observer regression checks for hits/events/drops, snapshots, and rejection of eight invalid inputs also passed.

The unit guest is synthetic ARM test code. The integrated executions below use original stock ARM main.

## Original execution comparison and performance

The two modes ran without a profiler, alternating full/scoped order five times each in new processes. They used the same image, one CPU, 512 MiB memory, original main, board, initial SRAM/ITCM, and device inputs. Full emulation was paused after ATT, then `RunFor(500ms)` reached the same virtual end boundary.

| Host execution time | Existing observation median and range | Selective suspension median and range |
| --- | --- | --- |
| Fixed 500 ms segment | 17.82 s, 17.31–18.34 | 1.77 s, 1.62–1.96 |
| Recorded total including build, initialization, and capture | 61.12 s, 60.86–65.88 | 45.94 s, 45.01–47.97 |

The virtual 500 ms segment itself was not shortened. Segment cost differed by about 10.05×, and recorded total time decreased about 24.8%. The segment is only part of total cost, so these numbers are distinct. They do not represent physical FPS, improvement across all scenarios, or successful full firmware boot. An earlier 15-second stack collection was excluded from the benchmark.

All five pairs had byte-exact main/board/initial inputs and complete initial, before/after ATT, and final SRAM. Recorded R0–R15, instruction count 85,808,849, and virtual start/end times also matched. Every run retained busy 362, request 2/trigger 1, calculations 0, and guard 0. The final dump did not cover all special registers, so do not claim the entire CPU state was verified.

## Preserved report differences

Raw reports are not identical. Besides selective-suspension metadata, two diagnostic timestamps for request and trigger were each 100 ns earlier. This is recorded as an observation difference equivalent to one instruction at the board's 10 MIPS. In the pinned frozen-core source those values appear only in reset/Now assignment/auto properties and are not read as control or timer inputs. Other runtime values matched.

No SRAM addresses were excluded. The original raw-value equality=false result is retained, and the fixed difference in two diagnostic clocks and equality of other state are judged separately. Three negative cases consistently forging JSON/log/hash for other clock drift, hidden SRAM changes, and source changed to remove all hooks were rejected.

## Tools and limitations

```sh
<private-python> tools/verify_observer_suspension.py <simulator> <new-audit>

# Select explicitly only in a new original experiment
<private-python> <trusted-local-wrapper> tools/probe_gaf_frozen_core.py \
  <simulator> <new-capture> --case stock24 --observe \
  --suspend-startup-observer --virtual-budget-ms 1000
```

The second command uses a research fault profile and exits 1 if the timeout is not observed. The original 200000-poll timeout, normal GAF computation, full app boot, and integrated display remain incomplete. This improvement concerns execution cost and state comparison for a pinned observation configuration. Reuse the explicit mode in later runtime/communication-failure experiments, proving each acceptance condition separately.

The first ownership fixture failed because a separate stop assembly import was missing; after fixing it, the RED run confirmed the actual API was absent. The first original-boundary test saw `RunFor` rejected because global emulation was still started after Machine.Pause. A small actual M55 test confirmed exact 1 ms advancement with PauseAll → RunFor before comparison with new output. Failed captures were retained and excluded from pass/speed evidence.

The saved audit passed five pairs and 95 checks; the frozen audit report was byte-exact. Three semantic negative cases and 14 progress-management checks also passed. Original integration execution comprised ten passing runs and one preliminary boundary API failure; other unit tests are distinguished as synthetic ARM.

Private evidence: `observer-suspension-native-{02..06}/{full,scoped}`, `observer-suspension-audit-02`, `observer-suspension-audit-frozen-01`, `observer-suspension-research-01/manifest.json`.

All 16 acceptance/status/evidence criteria and API 3/6 remain unchanged; overall progress is 7/16 (43.8%). No physical access, Astra/subagent, or external publication occurred.
