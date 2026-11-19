# Audit of sensor initialization and integrated UI dependencies

bw-0339 reused bw338 saved captures to examine the next IMU consumer and current display tasks together. **No new main run, peripheral model change, or screen success occurred.** Next priority is connecting the original display queue's 36-byte message producer and UI updates. Sensor initialization completion is not assumed to start the screen automatically.

## Current display state

Latest full SRAM and original PendSV frame contracts from three images were used. Active task candidates were checked against owner, count, sentinel, and index in actual bidirectional state lists. Each image had 29 linked tasks and current task `sensor_hub`.

The previous full task explorer failed on a container-0 candidate in the current snapshot. The new check records that one TCB-like candidate separately rather than including it in the active list. The current task cannot be excluded and failures of other container/link validation are not ignored. Whether that candidate is a freed task or another data structure remains undetermined. Previous results are not retroactively changed.

| Task | Currently observed wait |
| --- | --- |
| `ui_task` | queue receive, capacity 96 × item 12 bytes, messages 0, receiver 1 |
| `displaydrv_mgr_task` | queue receive, capacity 96 × item 36 bytes, messages 0, receiver 1 |
| `ambiqdraw` | notification counter, index 0, clear-on-exit 1, ticks `ffffffff`, value 0, waiting state 1 |

UI queue is `20074e10` in 2.4 and `20075868` in 2.3/CFW. Display queue is `20074e60` and `200758b8` respectively. Task saved R6, event-list container, and actual queue structures were checked together. Notification was bound using saved-frame call arguments and original callee prologue.

This differs from the `displaydrv_mgr_task` notification-bits wait in bw268's initial snapshot. Current task waits for a queue; the old notification wait is not reused as the current display bottleneck. Both queues are confirmed empty, but the external/internal event that must create a screen message is not yet verified.

Neither “finishing IMU automatically draws UI” nor “IMU success is necessary to start UI” is established. The current CPU stop on unsupported access in sensor_hub is distinct from causation of UI messages. Do not force initialization return to success or insert synthetic queue messages and report a normal main screen.

## Scale of the `02ae` consumer

Stock 2.4 getter is `5542c6..5545bc`, 2.3/CFW `52046e..520764`. Existing 500-byte function-boundary helper could not find its length, so bounded decode was expanded to identify the actual first return and 41 SRAM read callees. Firmware was not changed and execution was not skipped.

The function reads **41 fields, 153 bytes** into distinct output ranges and puts original constants `5000/2500` at output offsets `a0/a4`. Test buffer is 168 bytes and other padding is preserved. Full address/width/buffer-offset map is in a private report. Actual SRAM input values, meanings, and initialization results were not yet verified.

Running the original caller only until immediately before the first next helper overwrites just three ranges: byte at offset 0, words at offsets 4 and 8. Offset 8 is `0/40000` for gyro input 0/1. Remaining getter results stay unchanged up to that point. Later helper/setter use of defaults was not checked, so do not infer all fields are simply preserved.

Statically visible BL sites from after first prefix to initialization epilogue number 73 stock, 74 CFW. These include error logs and conditional branches; they are not counts of remaining executed calls or estimates of work. Do not open this large configuration sequence with 41 arbitrary zero responses and claim boot success. CFW has an extra call site `4b75be → 7d3338`. Prefix checks for three images stopped immediately before each image's first next helper; this extra hook body was not executed. Do not generalize that all initialization code is identical.

## Why return value alone cannot establish success

Active stack was bound using original prologues and actual BL return values: getter four-word frame, sensor initializer nine-word save + `134` bytes locals, and wrapper four-word frame. A coincidental code address in local buffer was not treated as a real call frame.

| Boundary | Stock 2.4 | Stock 2.3/CFW |
| --- | --- | --- |
| Sensor initializer | `4c2454` | `4b6d98` |
| Calling wrapper | `4c3210` | `4b7b54` |
| Initializer return to wrapper | `4c3246` | `4b7b8a` |
| Wrapper return upward | `4c61fc` | `4bab40` |

For valid modes the wrapper calls a subsequent helper and returns 0 without checking the lower initializer return. Standalone ABI controls giving the original wrapper lower results `0/fffffffd/ffffffff` confirmed this. Modes 5/255 are rejected without lower calls; mode 256 follows low-byte-0 path.

Current main remains stopped in lower initialization, so this does not mean error masking occurred in actual main. It is a source-supported return-path limitation: future boot-completion gates must not judge success from wrapper 0 alone. Check full startup state, required services, error records, and actual work together.

## Verification and limits

- 18 original getter, 36 caller prefix, and 45 wrapper conditions, 99 total. Getter SRAM reads and wrapper initialization/locking helpers are explicit ABI stubs. Caller prefix stopped before first helper execution.
- Engine is standalone Thumb analysis under Unicorn Cortex-M7 configuration, not a new natural Renode M55 main run. Current RTOS wait checks are read analysis of saved SRAM. Host did not change current task or fix queues/notifications.
- Three images, nine display tasks, and 29 active tasks each were listed and inactive frames checked. Frozen-rerun report/inspector artifacts are byte-identical.
- Eleven existing peripherals/observers retained hashes. 490 Python sources were pinned and syntax-checked, not counted as functional tests. Zero new native main runs.
- The first check failed because it required past display notification wait to remain current. Current frame/queue structures corrected this to queue36 state. That failure and earlier function-length/list check failures were preserved.

No full pixel/frame export or viewer review was newly performed. Empty queues and waits alone do not establish correct framebuffer or complete UI.

## Next execution sequence

1. Connect current `displaydrv_mgr_task` queue36 and original transmit function, identifying ownership, types, and lifetime of 36-byte messages. Do not declare a raw word a global handle or producer merely because it appears in code.
2. Find the causal relationship between actual UI update path and this queue. Do not treat the earlier type 7 producer/consumer contract as a general redraw command.
3. Define conditions to observe original main UI → renderer → framebuffer → display submission using legitimate input events through source-supported transport. Forced task wake or source-branch bypass is not normal-execution evidence.
4. Keep IMU 153-byte initial state as independent research. If needed, limit it to an explicit profile validated against public source/exact-version assets and actual consumption calculations, without claiming physical ROM identity. External ODR/FIFO and full initialization remain incomplete.

Code is `tools/inspect_imu_ui_dependency.py`. Proprietary inputs, full SRAM, and detailed reports remain outside Git at `~/Library/Application Support/Blackwall/simulator/imu-ui-dependency-source-02/`, `imu-ui-dependency-source-frozen-01/`, and `imu-ui-dependency-verification-01/manifest.json`.

Overall scope v2 remains **13/29 = 44.8%**. Web installation/independent recovery, full boot, integrated screen, and physical verification remain incomplete.

Follow-up bw349 [configuration consumption prefix and Faceclaw guard](imu-parameter-consumer-prefix.md) confirmed separate 12-byte calibration input, extra guard, and 41-field/153-byte preservation in the actual setter's first segment with 423 original ARM scenarios and frozen reruns. Full setter/natural main remain incomplete.
