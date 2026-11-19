# Touch and Ring Input Acceptance: Original UI and Display

bw-0488. **E11 was completed.** Declared v1 touch and ring inputs led to original task consumption and state/UI changes on stock 2.4, stock 2.3, and Faceclaw 38. Overall conditions are **15/16 = 93.75%**. The denominator and E11 acceptance wording were not changed.

Current v1 integrated inputs are touch wake plus additional source 1/code 4 scroll, and the existing `ring-wake` type 2/source 4/code 1 virtual relay. This does not mean arbitrary gestures or direct R1 BLE are supported. Other source-only/isolated input research remains labeled at its separate evidence level.

## Actual original input path

Pinned [bw486–487 touch evidence](../hardware/sensors-input/active-hud-touch-family-contract.md) was reused. All three originals showed GPIO27/IOM5 additional report → original UI command processing and return → 3,790-pixel scroll, while 40 samples in each 200 ms no-input control remained unchanged.

This work uses the existing [ring-wake](../hardware/communication/ring-public-scenario.md) path unchanged:

`Virtual opposite-temple UART relay → actual UART/timeout IRQ → original ring task/report → source 4/code 1 → actual service 108 send/ACK → original app state change → app 1 display request/response → UI callback entry/return → original render/packing → 576×288 frame`

The first report is `00096100020aa7e8030000`; storage of original ring tick 1000 was confirmed. The virtual response is tied to the actual outgoing ID and CRC. Faceclaw passed through the actual `0x7d5800` hook and `0x7d5812` fallback to generate its default HUD; the patch was not skipped.

## Ring runs and controls

| Original | First detail frame / counter after 100 ms | First frame raw SHA | No input from identical initial state |
| --- | --- | --- | --- |
| Stock 2.4 | 3 → 7 | Same as existing touch wake | No ring consumption/UI/frame for one second |
| Stock 2.3 | 3 → 7 | Same as existing touch wake | No ring consumption/UI/frame for one second |
| Faceclaw 38 | 3 → 7 | Same as existing touch wake | No ring consumption/UI/frame for one second |

Each first frame is 165888 bytes, SHA `5bed2a24…3501`. Original main/model/board/activation/probe and the execution prefix from main reset to just before input were compared with the pinned baseline. Pre-input registers, virtual time, and complete SRAM were also exact in each input/control pair. With no input, actual instructions ran on the same board while the UI remained asleep. The host does not write PC/SP/TCB, branches, returns, or guest SRAM.

The UI callback is the actual `ui_task` in type 2/Thread mode. It reaches the upper UI caller return point with the same TCB and a valid stack. Because of the dispatcher's original `PUSH {r1…r7,lr}`, SP at the return point is 32 bytes larger than at callback entry. The first host audit mistakenly expected equal SP and was retained as a failure; only the saved audit was corrected to match the original instructions.

The previously declared execution-rate input changing 10 → 167 MIPS was reused on the UI path. CPU registers, instruction count, virtual time, and all SRAM were preserved across the change. Controls where the UI does not open retain the starting rate. Thus this test verifies input and UI effects, not physical latency/FPS comparison. Each one-second control is longer than the virtual input-to-100-ms-follow-up-screen intervals of 635.3033/581.0122/579.8238 ms.

Existing limits of the cold sensor service and reference GPU functional model remain. This does not validate physical sensor mathematics, GPU/optical accuracy, or direct R1 wireless connection. All runs had zero guard, CPU/GPU, memory-policy, and cache violations.

## Tools and audit

`tools/run_ring_hud.py` extends only the existing ring runtime after UI entry on the E06 pinned board/model. No new C# device model was added. Run the input control with `--control` in a separate new output.

```sh
<private-python> tools/run_ring_hud.py <new-private-ring-output> --case stock24
<private-python> tools/run_ring_hud.py <new-private-control-output> --case stock24 --control
# Run stock23/cfw sequentially in separate outputs as well.
<private-python> tools/run_ring_hud.py <saved-output> --audit-existing --audit-output <new-private-audit>
python3 tools/audit_input_acceptance.py <private-simulator-root> <new-private-acceptance>
```

The existing ring audit was also reused to check actual report/send/ACK/state/UI entry; the new schema 2 audit checks UI return, frame, and subsequent lifetime. Execution-configuration integrity and semantic success are distinguished. Twenty-three audit dependency modules were frozen and six saved runs were checked from `/tmp` with empty PYTHONPATH. Normal/frozen reports are byte-exact. The independent E11 integration audit uses only stdlib; it does not rebuild the model or run ARM.

Nine semantic negative cases based on saved observations were all rejected: missing return, different TCB, wrong SP, stale frame counter, wrong time, GPU fault, and control UI frame/input consumption/timer incomplete. Execution inputs and original files were unchanged. The integration audit also rejects three cases: failure, missing case, and missing touch evidence.

The first integration audit mistook exactly one newline added while connecting the runner for a code change. Its failure report/source were retained, and the audit was corrected to check original prefix + exactly one newline and original prefix SHA. Source execution was unchanged and no new VM was repeated. The final integration audit is byte-exact with an independent source-only frozen run.

There were six new native runs: three ring input and three no-input controls. All six owned containers were confirmed absent from the actual Docker list. No physical access, flash/OTA/MRAM write, Astra/agent, or external publication occurred.

## Remaining overall goal

**E11 complete, 15/16.** Remaining E12 covers sensor samples → FIFO/IRQ → natural consumption by the original sensor task. Even after that, a final audit of all 16 conditions is required before completing the overall goal. The current number alone does not establish overall completion or physical validation.

Pinned originals, model, SRAM, frames, logs, and initial audit failure are outside Git in `simulator/ring-hud-*`, `input-acceptance-01..03`, `input-acceptance-frozen-01`, and `input-acceptance-manifest.json`.
