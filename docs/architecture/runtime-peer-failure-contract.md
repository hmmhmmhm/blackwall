# Runtime Peer Communication Failure Verification Contract

**Current assessment: E14 complete, overall 8/16 = 50.0%.** The [integrated acceptance audit](../research/peer-failure-acceptance.md) verified the original wording and nine pinned scenarios: three originals × disconnect/malformed message/delayed timeout and reconnection. Normal GAF, full app/physical recovery, and general observer noninterference remain unverified. Partial figures below are historical at their respective checkpoints.

Latest bw412 verified [stock 2.3/Faceclaw per-version recovery](../research/peer-recovery-version-profiles.md) using each original ABI. Long delay, actual timeout, reset/59 commands and 60 responses, original credit restoration, and new DM connection return were all confirmed. Detailed/minimal-observation SRAM is exact at three pinned boundaries; subsequent polling-time/SRAM differences are retained. Overall E14 assessment is integrated with existing disconnect and malformed-message audits.

Latest bw411 confirmed [stock 2.4 reconnection after timeout](../hardware/communication/post-timeout-reconnect.md): original credit 0 → 1, CCB release → new virtual LE event/IRQ → original DM handler return and CCB reassignment, zero guards/faults. New-connection ATT/full app and long-timeout paths for other originals were unverified; E14/overall 7 of 16 were retained at that checkpoint. Each follow-up below records its own checkpoint.

Latest bw410 confirmed [reinitialization advertising order](../hardware/power/post-reset-advertising-order.md) using full original buffers and added opt-in strict order for generation >0. New generation had 59 commands/60 responses, advertising 5/5, zero guards/faults, stopping immediately before credit store at original normal response 563d32. Credit restoration/new connection/app recovery and E14 remained incomplete; overall 7/16.

Latest bw409 confirmed [actual timeout return and internal notification consumption](../hardware/communication/controller-notification-consumption.md). Event 38 traversed original handler/dispatcher/free and progressed through 55 original initial commands/56 responses of the new generation. A subsequent original 2008 versus model 2006 advertising-order difference was retained at the IOM6 guard. App error display, full startup, recovery/E14 remained incomplete; overall 7/16.

Latest bw408 implemented [limited reset generations](../hardware/communication/controller-reset-generations.md). Original reset processed generation 1 handshake/two commands/two responses and reached timeout-callback return instruction 563d24 without guards/faults. Executing return, full asynchronous startup, app notification consumption, and reconnection were unverified. Existing default-off protection remained; E14/overall 7 of 16 unchanged.

Follow-up bw407 confirmed original reset 93 low/high, 17,784 µs pulse, and CS high ([reset boundary](../hardware/communication/controller-reset-boundary.md)). The adapter accepted release, but the single-use peer remained Exhausted and stopped at the RDY guard. Original/model were unchanged and existing complete SRAM/report values matched. Next was strict initialization per reset generation; recovery/E14 remained incomplete.

Follow-up bw406 explained the original timeout timing difference using the declared clock's RTOS 1024 Hz and WSF epoch/integer accounting ([results](../research/wsf-tick-accounting.md)). Original subtraction was 1+744+255=1000 ticks; additional observation's final full SRAM and existing report values matched. Physical clock/SI ten-second accuracy and controller-reinitialization recovery were unverified. bw405 actual completion-loss/timeout and bw404 delayed-reconnection evidence were also retained. At that checkpoint E14 was partial, overall 7/16 (43.8%); figures below are historical from bw377.

bw377, partial E14 verification. Prior bw375 completed E13 for overall 5/16 = 31.25%. This work reuses the same virtual connection runner. E14 requires verification of disconnect, delay, malformed messages, and original timeout/error/state, cleanup, reconnection or explicit failure.

## Original disconnect contract

Existing pinned Cordio source and the state tables of three originals were compared. H4 disconnect complete `04050400400013` is status 0/handle 0x40/reason 0x13. The original decoder produces event 3 and handle/reason; DM selects idle 0/action 4 from current state 3. Original close action deallocates the CCB and calls app close indication 0x28. Stock24 action is 0x4d400c, epilogue 0x4d4044; stock23/CFW are 0x4cdbcc/0x4cdc04. Per-original addresses derived from original code are retained in private close-contract.json.

An isolated ARM parser/decoder interpreted it normally. The full isolated HCI path stopped on existing UART1 0x4003a018 read and connection state remained. Do not count this as cleanup success. Source state-table interpretation is not a substitute for actual DM action execution.

After the same E13 original reset, phone input, and RTC-consumer return, a controller disconnect event is injected into the device model. The same GPIO117/SPI/HCI path is used; the host does not change guest PC/TCB/SP or connection bytes. The new peer option defaults off and accepts only exact handle/status and reason 0x13/0x08. It does not fabricate success ACKs for unsupported subsequent TX.

The predeclared budget is 20 virtual seconds from immediately before disconnect enqueue to the original close-action epilogue. Normal time-setting phase capture/RAM/JSON and disconnect capture are stored separately. Assess CCB inactive/state 0, original app close event/reason, WSF task/stack return, IRQ clear, RTC preservation, and zero faults/unsupported accesses. Do not extend endpoint evidence into advertising restart or reconnection after close action. Thirty-one unit checks for time limit/IRQ/pre-enqueue and duplicate/order rejection passed.

## Original execution results

| Scenario | stock24 | stock23 | Faceclaw38 | Assessment scope |
| --- | ---: | ---: | ---: | --- |
| Immediate disconnect 0x13 | 36 checks passed | 36 passed | 36 passed | Original CCB release/state 0, app close 0x28/reason, WSF/stack return, IRQ clear, RTC retained |
| XOR 1 only on final TPL CRC byte | 21 passed | 21 passed | 21 passed | ATT 0x842/permission 0 → actual TPL input 1 → app consumption 0/RTC 0, state/transmit queue retained |
| 1 ms delayed disconnect | 37 passed | Not run | Not run | CPU/task execute while timer injects device event at exact time and original handles close |
| 1000 ms delayed disconnect | Unsupported boundary | Not run | Not run | sensor_hub/IOM4 strict stop before input time; scheduled event did not occur |

Immediate-close input-to-endpoint virtual times were stock24 3.0477 ms, stock23 2.4166 ms, and CFW 2.4495 ms. These are pinned virtual-scenario values within the predeclared 20-second budget, not physical BLE speed or performance comparisons. Normal time-setting phase RAM/JSON were saved unchanged and close-phase RAM/JSON separately. Original tasks actually executed; no API caller or guest PC/TCB/SP/connection-flag seed was used.

The CRC control retained connection, MTU, ATT opcode, handle, and length, changing only the last TPL CRC byte. ATT return 0 does not mean malformed TPL was successfully handled. After ATT acceptance, the actual TPL parser discarded the message without app dispatch or RTC application. Do not extend this to verification of subsequent normal-message redelivery, full allocator cleanup, or reconnection.

Eight separate firmware-free unit tests for the 1 ms timer confirmed no event at 999 µs, event at 1000 µs, exactly 1,000,000 ticks, callback acceptance/rejection, reset cancellation, one-shot behavior, and range rejection. The native 1 ms test did not stop the CPU and merely advance time. It is delayed disconnect input, not proof of HCI command-response timeout or lost-packet retransmission.

The 1000 ms test stopped before the scheduled time at **1.2286 ms** in original `sensor_hub` TCB at PC 0x58236c/IOM4 guard 1. Timer fired=false. The older IMU component/board reused by the E13 communication runner lacked the GAF parameter class/profile, while the already verified latest 225-byte GAF profile had it. The specific IOM command was not exported in this capture, so do not assert an inferred command. This failure is a simulator support gap, not firmware timeout/recovery success. The aborted machine was not resumed and its container terminated.

## Saved audits and regression

New native runs comprised three immediate disconnects, three CRC cases, one 1 ms delay, one long-delay failure, and one feature-off control. The immediate-disconnect model's 31 unit checks and timer's eight are separate from original firmware execution. Peer changes are optional disconnect input and strict order/duplicate rejection; unsupported TX is not automatically ACKed. Reason 0x08 is allowed by input format, but only 0x13 was validated in this native work.

The complete feature-off peer report, 53 observation points/all events, and all SRAM matched existing main hold exactly. Saved audits of seven new successes, one off control, and three existing normal E13 captures passed 288 total assessments and matched original verification bytes. Two immediate-disconnect/CRC saved audits under the current frozen auditor also matched bytes. Old E13 audits inspect their pinned historical inputs/models/logs unchanged and are not retroactively regenerated with the current candidate builder.

Eight semantic mutations with consistent JSON/log/hash were rejected by CCB active, app-close event/task, time-budget, IRQ, app-state, RTC-write, and TPL-not-executed checks. CLI returned exit 1 for two mutated artifacts and the actual long-delay failure. Do not complete E14 based on success or test counts.

## Next assessment

E14 was **partial**, overall 5/16 = 31.25% (displayed 31.2%) and API 3/6. Original timeout for actual delay/loss, wait/cleanup, redelivery/reconnection or explicit failure remained.

Next integrate the already pinned and verified GAF component and board fixture into this runtime scenario. Check same main/peer/existing successful path and feature-off regression, and assess the original Sensor's next actual boundary. Do not consider the latest natural-main GAF service 7c000402 itself resolved. Do not repeat old 02ae-family research or delayed-value variants yielding the same strict result. Return to long-duration communication-failure testing after resolving original service effects/initialization return.

```sh
<private-python> tools/run_runtime_connection_m55.py <simulator> <new-output> \
  --case stock24 --att-time --disconnect-reason 0x13

<private-python> tools/run_runtime_connection_m55.py <simulator> <new-output> \
  --case stock24 --att-time --att-corrupt-crc
```

Add `--disconnect-delay-ms 1` for timed disconnect. In the legacy runtime profile, 1000 ms reproduces a support-gap failure and is not a product-success command. Saved audit uses `--audit-existing --audit-output <new-audit>`. Images, required source/templates, and evidence remain outside Git; missing assets are not arbitrarily substituted.

There was no glasses access, flash, OTA, persistent write, or external publication. Source and execution evidence are retained in `private:simulator/runtime-peer-failure-research-01`.
