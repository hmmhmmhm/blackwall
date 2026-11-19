# Original B2S Parameter Contract and Storage

bw-0336 analyzed the original get/set functions and connected parameter writes to virtual IMU RAM. This support covers **transfer and storage of 8 fields and 20 bytes**. It does not execute the B2S algorithm or the IMU-specific EDMP ISA. Original ARM main instructions, branches, return values, and firmware bytes were not modified.

## Actual data layout

Stock 2.4 getter/setter entries are `555c3c/555d0e`. The setter was bound using actual return/BL instructions in each image, and the getter's eight reads and caller were checked. Current main copies the following fields in order for usecase `0`. Physical units and meanings are not imported from a different structure in the latest public driver.

| IMU SRAM | Caller buffer offset | Length | Actual main value |
| --- | ---: | ---: | ---: |
| `1618` | 0 | 4 | 350 |
| `161c` | 4 | 4 | 3750 |
| `1614` | 8 | 1 | 7 |
| `1615` | 9 | 1 | 1 |
| `163c` | 12 | 4 | 50 |
| `1640` | 16 | 4 | 600 |
| `1638` | 20 | 1 | 7 |
| `1639` | 21 | 1 | 1 |

The original caller buffer was established by combining the actual call frame and `r1=sp+68` with the setter's six-word frame. Isolated tests use a 24-byte buffer and preserve offsets `10..11` and `22..23`. The getter overwrites only 20 bytes and the setter does not change the original buffer. The original function's byte copies were executed without reimplementing a numerical conversion.

For other usecases, a nonzero lower 8 bits selects address offset `-0e00`. `256` selected the default path because its lower byte is 0. This observes original code behavior and does not recommend arbitrary enum inputs. The native model currently supports only usecase 0 fields used by main.

The setter first reads `29/2a`. If `enable0 bit3` and `enable1 bit5·6` are all set, it returns `ffffffff` without writing. Otherwise it continues copying fields while accumulating errors with OR. This is a software guard in the original library, not evidence of hardware write protection in chip RAM.

The latest public B2S structure differs from the original in field count and layout. The distinction identified in bw334 between the original 375-byte image and the latest 1,310-byte image was retained; the public layout was not copied.

## Model changes

New writes are enabled only through the explicit `b2sParameters` option of `BlackwallImuPatchRam`. After loading the original image and service completion, the 20 addresses above may be modified once in the specified order. Other addresses, order, or a second copy are rejected before application. Values are treated as stored bytes; arbitrary sensor performance or events are not synthesized.

A valid first parameter write ends the remainder of the prior read cursor. Parent IREG readiness is also released only after a successful write to accept subsequent continuation. An invalid write does not first change reads or RAM. The values are written to the same model RAM and the actual stored field hex is read for diagnostic comparison. Code, dispatcher, and key regions are outside the permitted range of new parameter writes.

## Verification and next boundary

- All three original images recorded 20 bytes as `5e010000a60e0000070132000000580200000701`. Including 404 bytes of patch loading, total writes were 424 bytes. The previous prefix and two EDMP service completions remain.
- The next original request is `7c a2 7e 02`. In the fixed TDK regmap, `a27e` is `ACCEL_WOM_X_THR`. The write is not yet supported, so execution stops at a strict boundary before application. The descriptor's address 69, length 4, write direction, and actual payload, derived from the HAL prologue/caller, were checked in each capture's SRAM.
- Four final native runs (3 originals + 1 disabled) and four saved re-audits. The disabled control exactly matches bw335 CPU state and all selected events. No selected events were lost.
- 162 conditions for original ARM wrappers and 162 for frozen sources. Selector 0/1/256, bus state 0/error, and eight guard combinations were checked across three images. Register/SRAM callees are explicit ABI stubs. Isolated Thumb analysis with Unicorn Cortex-M7 is distinct from natural Renode M55 main execution.
- 1,565 unit checks and 1,565 frozen-source checks, cumulative including the existing 1,539. They check field order, outside addresses, read-to-write transition, neighboring bytes, rejection of a reset copy, and actual stored values.
- Ten existing peripheral/observer hashes were unchanged; only one IMU model changed. 485 Python files were frozen and syntax-checked. Syntax checks are not complete functional tests. The previous patch planner is otherwise identical apart from the current IMU SHA.

A baseline failure without the fifth constructor argument was confirmed first. The first native provisional `bounded-capture` semantic contract failed because it differed from the actual strict boundary; it was separately audited against the final strict contract without modifying the capture. Execution success and semantic contract success are recorded separately.

Tools are `tools/inspect_imu_b2s_parameters.py`, `tools/verify_imu_b2s_parameters.py`, `tools/renode-imu-identity.cs`, and shared planner `tools/prepare_imu_ireg_candidate.py`. Proprietary inputs, SRAM, and logs are preserved outside Git under `~/Library/Application Support/Blackwall/simulator/imu-b2s-main-01/`, `imu-b2s-saved-audit-01/`, `imu-b2s-source-01/`, and `imu-b2s-verification-01/manifest.json`.

Next, check WOM X/Y/Z thresholds, related configuration, and the B2S activation path as a behavior group. Then continue with external ODR, FIFO, and a nonzero main frame/viewer connection. Overall scope v2 remains **13/29 = 44.8%**. Full boot, app loop, integrated display, physical sensor, and real-device recovery remain incomplete.
