# IMU FIFO compression baseline and FSYNC software tag initialization

bw-0325. The advanced reset flow after [indirect endianness lookup](imu-indirect-endianness-peer.md) was connected using the original and pinned TDK code. This does not complete an actual sensor FIFO, FSYNC pin, or sample-processing model. New native runs start from original main reset; production firmware instructions, branches, return values, and observers were unchanged.

## Original state initialization sequence

Advanced reset in all three originals calls four functions: soft reset → endianness lookup → FIFO compression state initialization → FSYNC tag initialization. It clears software FIFO use/compression flags and frame size to 0; the compression function sets:

- Three accel, three gyro, and one temperature baseline halfwords: all 8000.
- Three kinds of baseline-found flag: all 0.
- The FSYNC function reads one byte of register 24 FSYNC_CONFIG0 and stores its low three bits at device context+2f.

These flags are internal driver state. Do not interpret them as actual sensor FIFO disable or successful compressed-sample operation. Original context structure and bit handling were compared with pinned TDK `inv_imu_driver_advanced.c`/register map.

`tools/inspect_imu_tags.py` verifies input main, RAM, saved audit, and upstream Git blob pins. It executes 2,310 independent ARM tests across the originals: two compression-initialization sentinel inputs and 256 FSYNC bytes × three read statuses per original. It checks baselines, neighboring-byte preservation, tags, returns, and stack restoration. This does not execute the entire sensor transport.

A key difference: even with nonzero read status, the FSYNC function stores the buffer byte's low three bits in the tag and returns the error status. This differs from the previously identified endianness getter preserving cache on error. It does not verify buffer contents after an actual failed read or whole-caller recovery. Distinguish this code's state update from its error return.

## Minimal model and reuse of existing tools

`fsyncConfig` in `tools/renode-imu-identity.cs` defaults to -1 (unsupported) and may be set to an explicit byte only with SREG/indirect bootstrap enabled. It returns the byte unchanged. The model does not perform tag masking or SRAM initialization in place of the original.

Only single register 24 select/read is supported; invalid lengths, reads before selection/after consumption, and configuration writes are rejected. Actual power-on values and allowed physical reserved-bit combinations are unknown. Normal 0 and control e5 are declared simulation inputs.

`tools/verify_imu_tags.py` checks 73 cases including existing checks and new tag lifetime checks. The missing-constructor red was also preserved. `--fsync-config` was added to existing `prepare_imu_ireg_candidate.py` to reuse pinned source/board/component/semantic plan. No new native runner is added per register. Omitting the option preserves the existing IREG preparation path.

## Natural M55 main and actual saved state

| Input | FSYNC fixture | Saved tag | Next boundary |
| --- | --- | --- | --- |
| Stock 2.4 | 00 | 0 | `58236c`, register 18 select |
| Stock 2.3 | 00 | 0 | `57b014`, register 18 select |
| Faceclaw | 00 | 0 | `57b014`, register 18 select |
| Stock 2.4 control | e5 | 5 | Same next boundary |

In four captures, actual SRAM confirmed seven baselines of 8000, found flags 0, FIFO software flags 0, frame size 0, and FSYNC tag 0/5. Context addresses were linked from previously verified actual frames and all original/capture file pins checked. No new CPU hook or RAM write observer exists.

After one FSYNC read, six total received bytes, and 16 successful I²C finishes, execution stopped at the next unsupported access. Previous observed event prefixes were preserved. The disabled control exactly matched the entire CPU state and observed events of bw324 IREG-only. There are five valid native runs and five saved audits. The first provisional boundary contract failure remains in the original report; it was verified by a separate audit changing only its own capture plan's semantic contract.

Next register 18 is INT1_CONFIG2. Sensor interrupt pin/routing, acquisition, and ODR/power configuration are not yet complete. This alone does not establish complete return of the advanced init function or application loop.

## Verification assets and next steps

All report values matched between 73 unit and 73 frozen checks. The 2,310 original and 2,310 frozen fragments also passed; source report/inspector artifacts were byte-identical. 467 Python sources were byte-identical to frozen source and passed syntax checks. This is not functional testing of all 467 tools. The default IREG plan matched the prior plan except for the explicit current model SHA.

Source, unit tests and frozen copies, capture, audit, and native state verification are preserved in private `simulator/imu-tags-verification-01/manifest.json`. Nine existing peripheral models were unchanged; only one IMU peer was extended.

Next identify INT1 configuration read-modify-write and subsequent power/ODR flow as behavioral units in the SDK and original. Extend with explicit inputs, state lifetimes, and error controls without filling unknown registers wholesale with 0. Then continue nonzero main draw and framebuffer/576×288 viewer.

Overall 13/29=44.8% and scope v2 remain. Web installation, Faceclaw CFW, recovery boot, integrated simulator, and screen are the overall goals. Full boot, UI, sensor samples, and physical recovery remain incomplete; this work involved no device connection, installation, or persistent writes.
