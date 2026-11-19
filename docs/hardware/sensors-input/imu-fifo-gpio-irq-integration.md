# Original FIFO watermark and GPIO38 IRQ integration

bw475. In FIFO configuration created by the stock 2.4.0.24 original setter, WM10 occurrence→INT1 pulse→GPIO38→NVIC57→original ISR/callback→return to the interrupted Thread was confirmed. A separate original FIFO consumption diagnosis then processed ten packets. The two stages follow in one run, but **this is not natural consumption caused by the IRQ callback waking the sensor task.** At gate 0 the callback returns along the original path without processing samples. E12 remains partial; overall 10/16=62.5%.

## Actual configuration and corrected assumption

[bw326 original INT1 configuration](imu-interrupt-configuration.md) sets the low 3 bits of register 18 to 1. With simulation reserved high bits the value here is 0xa1, but physical-device reserved bits were not measured. Under ICM-45608 DS-000595 rev1.1 §16.23 this is **push-pull, active-high, pulse**, not latch mode.

The initial connection sent threshold logical pending directly to pin level. IRQ, W1C, and consumption worked in that profile, but it did not match the original pulse configuration. Earlier native on/off01, 25 checks, and 85 audits were isolated as latch diagnostic evidence, not used as a successful stock profile. After comparison against original configuration and datasheet, a pulse timer was added and final evidence newly collected.

The §21.53 INT_PULSE_MIN_ON_INTF1 reset value 1 defines minimum-on 8 µs. This model uses that unchanged register's default as a **declared 8 µs pulse profile**, not a measurement of physical pulse length or exact clock domain/electrical delay. A 100 µs profile is also unit-tested; other polarity/open-drain and reserved settings are rejected. No claim is made to support pulse configuration changes during execution or all EDMP interrupt sources.

## Connection structure

`tools/renode-imu-int1-gpio.cs` is a small IGPIOReceiver receiving the existing threshold IRQ. It requires a machine, existing GPIO owner, and **explicit INT1 configuration**. The native recipe passes the existing IMU owner's actual `Int1Config2Value` and verifies low 3 bits=1. It does not copy the GPIO controller or existing configuration bank.

Threshold still has logical pending/status. In pulse mode, input rising raises the physical line profile and timer expiry lowers it. Even an early status read does not lower the line before minimum-on. An already-high input is not treated as a new rising edge. Not all silicon behavior for pulse recurrence/overlap and minimum-off has been verified.

Only with actual PINCFG38=0x93 does existing `TrySetPin38` accept rising. A high with invalid pad retains queue data but creates no GPIO edge and increments the rejection count. Changing the pad later does not create a past edge; the next actual low→high transition is required. Existing GPIO owner handles bank 1 enable/pending/W1C and NVIC57.

**GPIO W1C, physical pulse end, and FIFO status acknowledgement are distinct state changes.** GPIO pending can remain after pulse end until W1C, and threshold status remains until FIFO status read even after GPIO ISR writes W1C. Full device reset differs from individual GPIO/connector reset. This is not expanded into completed reset recovery during full execution.

## Final original M55 execution

The pinned cold baseline and original ARM code of [bw474](imu-fifo-native-configuration.md) were used unchanged. Only a new C# connector, opt-in pin38/NVIC57 wiring, and trace were added to the model. Main prefix and initial SRAM through getter, and SRAM after setter, were byte-identical to existing evidence.

| Stage | Confirmed result |
| --- | --- |
| Initial state | getter 0x5542c6, gate 0, frame 0, free IOM4 mutex |
| Original configuration | original 0x553196→R0=0, frame32, WM10, shared FIFO 0x2d/SMC 0xd8 |
| Sample input | 10×32 bytes, threshold rising 1, GPIO38 edge 1, NVIC57 pending |
| Injection invariance | Full SRAM, R0–R15, and virtual time identical immediately before/after injection |
| Original IRQ | ISR 0x4fc90e and callback 0x4c615e once each, IPSR73 |
| Original return | ITCM diagnostic caller 0x3ff40, original Thread/TCB/SP and R0–R15 restored |
| After IRQ | gate/timestamp 0, packet 10/consumed 0, GPIO W1C, pulse line low, threshold status pending |
| Separate API consumption | Original upper 0x4c38b0→IOM→parser/callback/ARM decoder 10 times each |
| Final | consumed 10, ring header [0x10203040,10,10], GPIO/threshold/line all cleared |
| Stop boundary | Immediately after parser return at 0x4c3ad0, R0=0, mutex returned, guard/fault 0 |

Source input and diagnostic callers involve host manipulation. This is an explicit API test, not passage through a natural main branch. The host does not write gate/TCB/IRQ mask/frame-size/ready. During the original IRQ stage, the pending interrupt executes without changing CPU PC and returns to the current caller. The consumption stage uses a previously declared separate caller entry. Full upper consumer return and natural sensor-task wake remain unconfirmed.

The final 2252-byte ring was exact against bw474 results verified with earlier independent formulas. `completed6` is the cumulative adapter lease count for two configuration reads + four consumption reads, not the total physical I²C command count.

## Verification and preservation

The final 36 checks of `tools/verify_imu_fifo_gpio.py <private-simulator> <new-output>` use actual Renode IOM/GPIO/NVIC and timer. This is a standalone fixture without main ARM execution. It includes default off/missing owner, invalid input number, WM, mask/W1C, held-high, pad, source reset, pulse 8/100 µs, early ack, and timer reset. Existing threshold/configuration/ODR components were unchanged; existing regression evidence was reused after confirming bw474 frozen source hashes matched current inputs. These suites are not counted as newly rerun this time.

The final native pair is private `imu-fifo-gpio-native-on-02` and `imu-fifo-gpio-native-off-02`. Essential IRQ entry/return observation remains in the control with optional setter/consumer/IRQ trace hooks off. It is therefore not a run with all observers removed. Equivalence of SRAM and WORK at initial, post-configuration, before/after injection, post-IRQ, and final stages is audited separately.

The audit uses only inputs in private `imu-fifo-gpio-research-01/frozen`, without retrospective references to current ROOT/builder. Initial latch source/audit are preserved in `frozen-latch`, `audit-latch.*`. Platform-load missing-class red, two unit preparations failing due to wrong Renode object names, and pulse constructor missing red are excluded from success. Final saved audit passed 103 checks, and all 12 owned containers were removed and absent in Docker inspect. SHA256 asset list is preserved in private `simulator/imu-fifo-gpio-manifest.json`.

The next key gap is **normal GAF/EDMP computation→initialization return→natural original sensor-task wake/consumption**. Do not force gate open or write ready in its place. Unsupported computation is not replaced with timer completion or static results to judge normal boot. No physical access, flash, subagents, or external publication.
