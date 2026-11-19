# PMIC LDSW/LDO Configuration and Subsequent Original ARM Execution

Work bw-0152. Modeling LDSW/LDO configuration and requests allowed original stock and Faceclaw ARM to progress past the current PMIC initialization boundary to MCU `0x40008900` read. This is not full boot, main-loop, or display success.

## Source and model scope

`npmx_ldsw.c`, `npmx_ldsw.h`, `npm1300.h`, and `npm1300_peripherals.h` from Nordic npmx commit `4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f` are preserved privately in `simulator/npmx-ldsw-research-01`. SHA-256 and existing pinned Git tree blob IDs were checked. [Driver source](https://github.com/nordicsemi/npmx/blob/4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f/drivers/src/npmx_ldsw.c) is BSD-3-Clause; Nordic IC usage restrictions in ADK headers are separate. Originals were not copied to Git.

[Official nPM1300 description](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/loadsw/doc/frontpage.html) distinguishes LDSW/LDO mode selection, voltage configuration, task/GPIO control, and soft start. GPIO is edge-driven and output also depends on input power, so rail state is not synthesized from settings alone.

| Address | Register | Declared initial stored value | Allowed codes |
| --- | --- | --- | --- |
| 0805/0806 | LDSW1GPISEL/LDSW2GPISEL | 00/00 | bits 0–3: GPIO selection/inversion |
| 0807 | LDSWCONFIG | 00 | eight bits: soft-start/discharge configuration |
| 0808/0809 | LDSW1LDOSEL/LDSW2LDOSEL | 00/00 | 0 LDSW / 1 LDO |
| 080c/080d | LDSW1VOUTSEL/LDSW2VOUTSEL | 00/00 | 0–23, raw voltage code |

Write-only tasks 0800–0803 are LDSW1 set/clear, LDSW2 set/clear in order. Single byte 0 has no effect; 1 records request count. This is not evidence of completed output enable/disable. 0804 LDSWSTATUS and reserved 080a/080b remain unsupported.

A final optional `ldswState` argument was added to both PMIC constructors:

- null: existing strictly unsupported state.
- guest-storage: initial unknown; only guest-written bytes readable.
- source-reset-storage: explicitly declare seven initial stored values above.

The direct peer API can read/write 1–5 consecutive configuration bytes at once. Actual IOM fragmented 4+1-byte reads are not yet supported: Read(1) after first Read(4) is blocked by pending guard. Current original path reads one LDSW byte, so main results below are unaffected. Reserved areas beyond 0805–0809 and 080c–080d are not allowed. The whole burst is validated before storage so an invalid later byte cannot change only earlier bytes. Invalid widths, overlapping transactions, WO task reads, and status writes are blocked. Values and request arrays are returned as copies. Reset restores selected fixture's stored values/unknown and empty diagnostics; it does not mean actual power reset or soft start.

## nPM1300 and nPM1304 boundary

Pinned latest `npmx_ldsw_mode_set` first reads `0208` and, in certain modes, manipulates a soft-start bit for nPM1304 rev >= 1.1. [nPM1304 documentation](https://docs.nordicsemi.com/r/bundle/ps_npm1304/page/chapters/core_components/loadsw/doc/frontpage.html) also describes a separate procedure based on build code. This was not automatically applied to nPM1300/G2. Reads/writes of `0208` are unsupported in this model and unit tests confirmed blocking.

Original ARM did not follow this latest SDK call path unchanged in the observed interval below. The difference remains a subject for SDK version, PMIC revision, and call-path investigation. Entire current SDK function and stock binary equivalence is not claimed.

## Original ARM results

`tools/probe_pmic_ldsw_main.py` uses the immediately previous BUCK run as pinned input. Original bundle/raw main hashes and bytes, initial fills, all non-PMIC model sources, and runtime except observations were preserved. Guest instructions, branches, and returns were not forced. This begins at existing main reset, not evidence of ROM/full boot.

| Condition | LDSW observation | End boundary |
| --- | --- | --- |
| Stock 2.4 / source-reset-storage | 0808 read 00 → write 01, 080c write 08, 0800 write 01 | MCU 40008900, four-byte read |
| Stock 2.3 / source-reset-storage | Same | Same |
| Faceclaw 38 / source-reset-storage | Same | Same |
| Stock 2.4 / guest-storage | Initial mode unknown, no write | Existing 0808 address write, width 2 |
| Stock 2.4 / null | No write | Existing 0808 address write, width 2 |

Selected conditions' final configuration is `[0,0,0,1,0,8,0]`, with two configuration writes, one task write, and task requests `[1,0,0,0]`. This selects LDSW1 LDO, stores voltage code 8, and requests enable. Actual LDO voltage, rail activation, GPIO edges, soft start, and discharge response were not implemented.

The three originals have two ADC completions each for VBAT/NTC/IBAT, existing four returns/11 bytes, and watchdog start 0. Stock 2.3 and Faceclaw used the same model/runtime with only main size differences allowed. Seven inputs other than board selection are identical across the three stock 2.4 profiles.

New stop PC is `4a2d9a` for stock 2.4 and `49d1d2` for stock 2.3/Faceclaw. This is now general MMIO guard `40008900` read, not PMIC pointer guard. **Register meaning at this address had not yet been established.** No arbitrary 0 or ready was returned. Next compare exact source/SVD, executing instructions, and call path.

## Verification record

- Unit 01: preserved red log failing due to missing new constructor argument.
- LDSW unit 02: 263 passed including existing BUCK/charger status tests.
- Post-review unit 03: 266 passed, adding fragmented-read blocking and new-transaction resumption. Production model and main were unchanged.
- Queued ADC unit 06: 401, scalar ADC unit 09: 408, watchdog unit 14: 240 passed.
- Original main 01: all five conditions above completed and verified.
- Recovery feed 15: five ARM-function conditions compiled from pinned watchdog.h passed with existing synthetic power/pin/DWT/hole assumptions.
- Saved audit 02: 196 passed. Compared source pins, RW/WO/reset, voltage-code limits, revision-specific source existence, original bundle/raw, full model-source reconstruction, observation-only runtime, fills, settings/requests, controls, regressions, and feed.

Evidence is preserved privately in `simulator/pmic-ldsw-unit-01`, `pmic-ldsw-unit-02`, `pmic-ldsw-unit-03`, `pmic-ldsw-main-01`, `pmic-queued-unit-06`, `pmic-adc-conversion-unit-09`, `pmic-timed-unit-14`, `recovery-pmic-feed-15`, `pmic-ldsw-verification-01`, and `pmic-ldsw-verification-02`. Docker runs were sequential; execution sources were not modified during runs.

Reading review by a non-Astra agent inheriting the parent model found no significant implementation error. Review requested distinguishing direct peer API and fragmented IOM reads; documentation and unit tests were strengthened. Differences between configuration/requests and actual output, and between latest SDK and original call path, remain unverified. Exact model ID, separate model-family review, and an unavailable transcript archive audit are not claimed complete.

Overall product progress is 13/29 (44.8%). Goals of web installation, recovery boot, development simulator, and display remain in progress; this result alone does not complete full main loop, display, or installation/recovery readiness. No glasses connection, RAM payload, OTA, permanent write, or Astra execution occurred.
