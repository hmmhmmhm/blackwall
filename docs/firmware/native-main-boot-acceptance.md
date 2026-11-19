# Original Main Boot, Task Wait, and Resume Acceptance

bw-0483. **E05 was completed.** On a declared virtual board, stock 2.4, stock 2.3, and Faceclaw38 passed original main reset → required initialization path → actual RTOS app events → queue wait → event resumption of the same task. Overall conditions are **13/16=81.25%**. The existing 16 conditions and denominator were unchanged.

This is a pinned scenario for a functional emulator starting at main. It does not mean original Boot ROM/bootloader execution, every product feature, long-term stability, or physical power, speed, or sensor mathematics were verified. Faceclaw follows the stock UI fallback path through an actual patch hook.

## Directly captured wait → resume

In all three runs, an existing virtual timer pauses the whole machine 10 ms after the first screen. Full SRAM, general registers, current TCB, instruction count, and virtual time are read, then execution resumes unchanged. The original UI task's waiting state and later execution were paired chronologically.

| Original | Actual UI TCB | Empty UI queue | First original callback after wait capture | Total observation after first screen |
| --- | --- | --- | ---: | ---: |
| Stock 2.4 | `0x200203b8` | `0x20074e10` | After 4.755 ms | 100.775 ms |
| Stock 2.3 | `0x2001e090` | `0x20075868` | After 4.873 ms | 100.187 ms |
| Faceclaw38 | `0x2001e090` | `0x20075868` | After 4.815 ms | 100.130 ms |

All times are virtual. Queue capacity is 96, item size 12 bytes, and message count at capture 0. Sentinel, bidirectional links, owner, and count were checked to establish that the actual TCB's event-list item belongs to the queue receive-wait list. The queue handle slot was derived from original UI producer Thumb LDR and compared with the same queue to avoid mistaking the pending-ready list for the receive-wait list.

Later, the same TCB entered the original app1 callback with event type 4. Callback PC, Thread mode, and timestamp later than wait time were confirmed. Initial app1 event type 2 was also observed on the actual original path. Type 4 callback counts after wait capture were five for stock 2.4 and four for the other two originals. Differences are not interpreted as physical performance differences.

General registers, tick, instruction count, TCB, and device state matched before/after SRAM read. Host did not insert queue waiters or make tasks ready. Resume restarts machine execution without writing PC, TCB, branches, or returns.

## E05 requirements and evidence

| Requirement | Actual check |
| --- | --- |
| Run three originals from main reset | Full size/SHA per original, Thumb PC/SRAM SP from original vector, main load/vector execution path in pinned `.resc` |
| Pass required service initialization | Observation points for PMIC init return, NOR address-mode/NVdb return, LittleFS format/remount/app-init return, GPIO role, timer setup, font manager, and UART power return |
| Declared peer/sensor readiness path | Virtual controller peer Complete and actual command/frame handling; original sensor wrapper return gate 1 and FIFO configuration ready |
| Actual RTOS app events | Actual UI callbacks for initial type 2 and periodic type 4, original TCB, Thread mode |
| Task progress and wait/resume | Actual receive-wait list of empty original UI queue → later same-TCB callback → instruction count progress |
| No errors | Guard accesses, CFSR, HFSR, memory-policy violations, GPU rejection/fault all 0 |
| No forced CPU/firmware changes | Pinned main/board/model SHA, no PC/TCB/branch/return seeds in execution script, six initial SRAM snapshots byte-exact |

All three reproduced previous first-screen raw SHA and confirmed five completed frames, serial 3→7, content changes, and sleep entry/exit. There was no task-trace overflow. NVIC sleep history overflowed its 128-entry limit, so total IRQ/sleep counts are not claimed.

This initialization-path check does not claim every underlying API returned 0. For example, the declared empty storage performs format/remount after first mount, and missing default font header follows original fallback. Sensor gate 1 is wrapper-return evidence, not a numerical GAF-success verdict. Scope retains user-approved cold-sensor, virtual-peer, and reference GPU functional profiles.

## Execution and audit tools

`tools/run_post_screen_lifecycle.py --task-wait-probe` adds an optional 10 ms observation boundary to existing schema 2 execution. Default options and prior saved audits remain. No new device model or C# observer was implemented.

`tools/audit_native_main_boot.py` reads saved three-original runs and pinned audit results to assess E05 as a whole. It does not rebuild models or execute ARM. If any case is missing or fails, E05 does not pass.

```sh
<private-python> tools/run_post_screen_lifecycle.py <new-private-output> \
  --case stock24 --task-wait-probe
# Run stock23 and cfw sequentially, each with a separate new output.

<private-python> tools/run_post_screen_lifecycle.py <saved-output> \
  --audit-existing --audit-output <new-private-audit>

<private-python> tools/audit_native_main_boot.py \
  <captures-root> <saved-audits-root> <new-private-acceptance>
```

Three new ARM runs were performed, one per original. Removal of all containers and absence of the three owned containers from actual Docker listings were confirmed. Nine Python audit modules were frozen and independently checked from `/tmp` with empty PYTHONPATH. The corrected final integrated audit's ordinary and frozen reports are byte-exact.

## Checking rejection of failures

Three cases with modified saved material all passed execution-configuration integrity but were rejected by task semantic checks:

- Original UI queue handle and wait-list connection did not match.
- Callback after wait ran in another TCB.
- Callback timestamp preceded wait capture.

If a failure report for one original is inserted into the integrated audit, E05 fails overall even if the other two pass. No new guest execution was added.

The first integrated audit mistook the third `MAIN_LAYOUT` value, bundle size, for reset vector. The initial failure report and code were preserved. It was fixed to unpack named fields and read original vector from actual main header. Original size/SHA, vectors, and execution material were unchanged; success was not produced by rerunning model or firmware.

## Remaining overall goals

E05's declared pinned boot, app-event, and task wait/resume scenario is complete. Next is **E06: virtual reset and reinitialization in active device state**, followed by E11 additional input and E12 sensor-sample consumption. No physical access, flash/OTA/MRAM writes, agent calls, or GitHub publication occurred.

Originals, SRAM, frames, and pinned reports remain outside Git in `simulator/ui-task-wait-native-01`, `ui-task-wait-frozen-audit-01`, `ui-task-wait-negatives-01`, `native-main-boot-acceptance-01..03`, and `native-main-boot-manifest.json`.
