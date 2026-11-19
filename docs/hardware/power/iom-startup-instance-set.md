# IOM Startup Instance Set

bw-0122. The existing bounded polling/CQ model is independently connected to modules 5/7 in the stock registration table. Work occurs without device access; DMAEN and unsupported-peer blocks remain.

Pinned DFP SVD/header confirms:

| Module | Base | NVIC | Power mask |
| --- | --- | --- | --- |
| 2 | 0x40052000 | 8 | 0x8 |
| 4 | 0x40054000 | 10 | 0x20 |
| 5 | 0x40055000 | 11 | 0x40 |
| 7 | 0x40057000 | 13 | 0x100 |

Modules 5/7 inherit IOM0 register layout. In the actual pinned stock24 registration-table snapshot, config pointers for 2/5/7 were all 0x20002a0c. Existing capture of that configuration is mode 1, requested 400 kHz, NBptr 0/len 0. Actual configure writes and measured bus clock require separate confirmation. Table 7 handle 0 at that time was pre-initialization, not hardware absence. Evidence: `private:simulator/iom-startup-instance-research-01/report.json`.

Select with `--iom-modules 2,4,5,7`; default remains 2. Only selected modules' 0x400-byte ranges are separated from the strict guard. Power objects, registers, CQ state, and IRQs are independent. `--iom-power-profile 5:stuck-off` independently overrides a selected module's response. Existing module 4 option remains but duplicates with generic override are rejected. This is a virtual fault profile, not physical state. Duplicate, unselected, and unsupported overrides are not silently overwritten.

Default unknown CQ input and explicit mock-pin scenarios remain distinct. Assuming pin 0 to observe original startup does not verify actual MSPI/GPIO/IOM/BLE signals.

## Verification results

Standalone adapter 82, CQ 79/mock input 43, and shared bank 52 conditions were verified on the new core. Shared tests include NVIC pending/clear for IRQ11/13, IOM5/7 CQ flag isolation, preserving other controllers' clocks/flags when IOM5 is off, and blocking unselected IOM6/neighboring addresses. This is not CPU ISR execution. `verify_iom_board.py` checks guard continuity for 15 selected subsets, 12 invalid inputs, and exact ValueError for three CLIs. UART 117/shared 28 were also rechecked with the modified core.

Three originals in `private:simulator/iom-startup-main-comparison-01` strictly stopped at CLKGEN.OCTRL (0x4000400c) read after configuration/off of all selected IOMs. PC is 0x506c20 for stock 2.4 and 0x4e8394 for stock 2.3/Faceclaw38. IOM5/7 each had six writes/20 reads and MI2CCFG 3f270. This does not mean the full startup function completed or actual I2C communication succeeded.

Each IOM2/4/5/7 stuck-off profile blocked an unpowered FIFOTHR configuration write for that module. States of earlier modules and later not-yet-started modules were checked separately. This does not prove the same physical failure or safe fallback. Current-source default unknown was separately run, confirming IOM2 CQFLAGS read blocking remains.

Actual stock24 module 5/7 handles were captured read-only for 32 bytes, matching mode 1 and NBptr 0/length 0. Registration table 7 handle changed from initial 0 to 0x20042520; initial 0 is not interpreted as hardware absence. The meaning of these stock24 addresses is not copied to other firmware.

UART1 was enabled a second time before the new stop: writes 34/requests 2/responses 3/off 1. TX bytes and UART ISR entries are 0. The first auditor failed assuming writes 26 from the previous stop. Expectations were updated for additional initialization on the current path; firmware/execution were not altered to fit. Failure summary is preserved in `iom-startup-verification-01/audit-failure.json`.

A Python SyntaxError in fixture editing failed before native startup. The parser was cleaned up and embedded Python driver precompiled before running. This is recorded in `iom-startup-verification-02/fixture-edit-failure.json`, separate from successful native results.

`iom-startup-verification-02/report.json` confirms agreement of 22 sources, combined C#, host source, raw logs/reports, original SHA/vector, 36 DFP masks, stock 2.3↔CFW scripts, and verification material above. Independent same-GPT-6-family review found no additional significant issue. Other model-family and archived transcript comparison were not performed. Actual CQ pairs/I2C commands are 0; DMAEN, physical inputs/timing, full boot/display, and installation verification remain incomplete. Next investigate CLKGEN.OCTRL RTC oscillator selection and initial-state contract. Product progress remains 13/29.
