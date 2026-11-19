# HFRC2 and MCU Performance Transition Response Model

Status: limited clock response and original main initialization verification complete. This is not full boot, display, or real-device installation verification.

## Original code and model

Pinned Ambiq HAL `61b293a49db34030c545f99101f7ebf6a3050314` `am_hal_pwrctrl.c:mcu_hp_lp_switch_sequence` sets `CLKGEN.MISC.FRCHFRC2` when selecting HP, waits for `CLOCKENSTAT.HFRC2READY`, then requests `PWRCTRL.MCUPERFREQ`. ACK and actual STATUS checks are separate. Even after force is released, HFRC2 is modeled as remaining on if an HP consumer uses it.

- `0x40004044`: MISC, force bit 5. The earlier buck document's CLKCTRL label was incorrect and corrected; CLKCTRL is `0x40004120`.
- `0x40004030`: CLOCKENSTAT, enabled bit 31 and ready bit 24.
- `0x40021000`: MCUPERFREQ, REQ bits 1:0, ACK bit 2, STATUS bits 4:3.

`tools/simulator_mcu_clock.py` and native `BlackwallMcuClock` supply this digital response only in selected scenarios. Initial LP=13/HP=22 are existing synthetic states. Nominal ACKs a request and changes to HP without delay. Unready does not supply ready; no-ack retains ACK=0 and existing STATUS after a request; denied retains ACK=1 and existing STATUS. Transition back to LP is unsupported. Other CLOCKENSTAT fields are assumed 0.

Actual frequency, stabilization time, voltage, power consumption, upper MCUE fields, and full clock mux are not modeled. This is virtual behavior based on material and instructions, not a G2 measurement.

## Executor boundaries

The Python approximate executor stops on SHCSR `0xe000ed24` read. The original instructions are normal MPU-disable code clearing MEMFAULTENA and MPU CTRL ENABLE. SHCSR access alone does not establish fault-handler entry or firmware failure.

Renode M55 executed that code and advanced to the next power register `0x40021090` read. In between it added 2,048 cache clean-invalidates, one geometry query and selector write each, and one buck status query. The executors are not claimed to have identical endpoints or all cumulative access counts. `compare_dcache_startup.py --buck-response active --mcu-clock-response nominal` compares common clock state and existing cache/trim state and explicitly checks these extra accesses and different endpoints. Native is not stopped to match the Python endpoint.

A synthetic M55 test confirmed MPU CTRL 5→4 and SHCSR MEMFAULTENA 1→0 under privileged default map. This does not prove all MPU region permissions or TrustZone accuracy. The M4f control stops with a fault on an existing MVE instruction.

## Verification material

The 12 native conditions in private `simulator/mcu-clock-native-guard-01/report.json` include nominal, unready, no-ack, denied, force unset, reserved bits, byte writes, writes to read-only state, invalid requests, and repeated requests. Five normal/failure response observations ran to completion sentinel. Seven invalid-access rejections stopped at the first unsupported access and did not execute the later sentinel write.

The synthetic MPU control test is preserved in `simulator/mcu-clock-mpu-smoke-01/report.json`. Six actual main combinations in `simulator/mcu-clock-main-comparison-02/report.json` (stock 2.3/2.4/Faceclaw × LP/HP) passed the limited comparison above. Native final PC is `0x4889ae` for stock 2.3/CFW and `0x494896` for stock 2.4; all stopped at `PWRCTRL.GFXPWRSWSEL` (`0x40021090`) read.

Python `simulator/mcu-clock-verification-01/python-regression.json` contains 122 checks across eight specified modules with zero failures/errors/skips. It does not mean the entire repository test suite passed. Public header fields/offsets were confirmed by compile assertions in `tools/verify_mcu_clock_sources.py` (`simulator/mcu-clock-source-audit-01/report.json`).

The first comparison `mcu-clock-main-comparison-01/progress.json` failed because it did not expect the additional cache sweep. Comparison scope and exact difference checks were corrected without changing the execution model. First native results and earlier stock 2.4 LP results were reused after checking source, hashes, and options.

The full main app loop, display driver, framebuffer viewer, BLE, and sensors are not yet connected. No physical glasses access, RAM execution, OTA, permanent writes, or external publication occurred.
