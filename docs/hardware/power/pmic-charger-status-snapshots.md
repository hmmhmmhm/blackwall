# PMIC Charger Status Snapshots and Original ARM Execution

Work bw-0150 added a model explicitly selecting six read-only states from the [static contract investigation](pmic-charger-status-contract.md). Original stock 2.4, stock 2.3, and Faceclaw ARM received one status byte and progressed to the next `0x040f` address request. This is not full boot, main-loop, or integrated-display success.

## Implementation scope

A final optional `chargerStatusProfile` argument was added to `BlackwallPmicRestoreProbe` and its `BlackwallPmicTimedProbe` wrapper. Existing calls default to null and retain the current unsupported boundary.

| Selection | 032d/0332/0333/0334/0336/0337 values | Meaning |
| --- | --- | --- |
| null | All unsupported | Existing behavior without inferring status |
| source-reset-snapshot | 00/00/00/00/00/00 | Virtual snapshot explicitly fixing source-documented initial values |
| battery-detected-idle-snapshot | 00/00/00/01/00/00 | Fixed virtual snapshot with only battery-detected bit 1 |

Neither profile is **coupled to time, ADC results, or charger configuration**. The name `source-reset-snapshot` does not mean an actual power reset was reproduced. In particular status 0 also means battery-detected bit 0; the combination with the existing discharging IBAT fixture is not claimed to be consistent actual PMIC behavior. 01 is not a charging or fully charged indication either. Both snapshots compare original execution under input assumptions.

Only 1–3 consecutive bytes within supported addresses are returned. Reads of 0332–0334 and 0336–0337 are possible, but **reads crossing reserved address 0335 are rejected**. Status-register writes, unsupported clear/release tasks, invalid widths, and overlapping transactions remain blocked. The existing root subset requires STOP after address write and continues to block reads immediately after pointer write without STOP. This is not presented as physical repeated-START support. The watchdog's separate repeated-START path retains existing behavior.

Values, addresses, and read history are returned as copies. Cumulative status reads/bytes and the most recent 64 addresses/full payloads are recorded separately. Model Reset initializes the fixture back to its declared snapshot and empty diagnostics. Reset of error FSM, voltage, charging, and protection functions is not implemented.

## Actual original ARM results

`tools/probe_pmic_charger_status_main.py` copies eight input files from the existing queued main, changing only PMIC source suffix, profile, and observation output. It verifies hashes and bytes of three pinned bundles/raw mains. Guest branches, returns, instructions, initial SRAM/ITCM fill, and execution policy were unchanged. This is the existing path from main reset, not new verification of ROM/full boot execution.

| Condition | 0334 return | Next unsupported request | VBAT/NTC/IBAT completions |
| --- | --- | --- | --- |
| Stock 2.4 / reset snapshot | 00, one byte | 040f address write, width 2 | 2 each |
| Stock 2.3 / reset snapshot | 00, one byte | 040f address write, width 2 | 2 each |
| Faceclaw 38 / reset snapshot | 00, one byte | 040f address write, width 2 | 2 each |
| Stock 2.4 / battery-detected snapshot | 01, one byte | 040f address write, width 2 | 2 each |
| Stock 2.4 / no status selection | No return | Existing 0334 address write, width 2 | 1 each |

Selected cases observed four ADC requests and two automatic IBAT requests, with completion order `[0,2,1,0,2,1]`. Each channel completed once more than previously, but this is not evidence of a periodic app loop or completed charging FSM. Die/VSYS/VBUS completions remain 0. Previously returned ADC data remains four reads/11 bytes; additional conversion completion is not confused with additional data reads. Watchdog is start 0/stopped.

Stock 2.3 and Faceclaw use the same model and runtime, allowing only main size differences. The stock 2.4 0/1/unselected comparison also has seven identical inputs except the board profile. Reaching the same boundary with 0 and 1 does not prove all subsequent behavior equivalent. An SRAM window interpreted as float at the previous 0334 boundary has different content at this boundary, so the same address is not treated as a permanent sensor structure and the earlier interpretation is not automatically applied.

Current PC remains 58236c for stock 2.4 and 57b014 for stock 2.3/Faceclaw. Because execution stops in the same IOM command handler, progress is judged by **newly returned payload and next request value 040f**, not PC. LastAddress is the previous pointer; LastValue is the requested address.

## Verification record

- Status unit 01: preserved a red log failing due to the absent ninth constructor argument.
- Status unit 02: 118 checks passed including existing defaults. Values, RO/reserved blocking, resumption after failure, overlapping-transaction blocking, diagnostic counts, copying, and reset were checked.
- Queued unit 04: 401, existing scalar ADC unit 07: 408, watchdog unit 12: 240 passed.
- Original main 01: all five conditions above completed and were verified. No separate physical access.
- Recovery feed 13: five ARM-function conditions compiled from existing pinned watchdog.h passed. The first CLI invocation omitted the recovery path argument and exited 2 before execution; it was rerun with correct arguments. Already-passed ADC/watchdog tests were not repeated. Existing power/pin/DWT/status-hole assumptions remain.
- `verify_pmic_charger_status_evidence.py`: 163 comparisons of saved originals, sources, logs, unit, and feed results passed. It does not execute a new guest. Review after the initial 158 checks added a byte-preservation comparison for the start of the PMIC suffix, increasing the count to 163.

Evidence is preserved privately in `simulator/pmic-charger-status-unit-01`, `pmic-charger-status-unit-02`, `pmic-charger-status-main-01`, `pmic-queued-unit-04`, `pmic-adc-conversion-unit-07`, `pmic-timed-unit-12`, `recovery-pmic-feed-13`, and `pmic-charger-status-verification-02`. Docker ran sequentially; subsequent runs and source edits occurred only after each session's termination was confirmed.

## Next boundary and overall goal

In the pinned ADK header, `040f` is `BUCKSWCTRLSEL`. It has not yet been modeled or answered. Next, rather than passing only this register with 0, investigate BUCK voltage, enable, mode, and GPIO/software selection as a group for source/reset/guest-write contracts. Causality between tasks and actual rail states is distinct from digital configuration storage.

Product completion remains 13/29 (44.8%). Overall goals of web installation, recovery boot, and CFW development simulator remain in progress. This result does not satisfy physical recovery, main loop, display, or final installation readiness. No Astra, device connection, RAM payload, OTA, or permanent write occurred.

Review was read-only by an existing non-Astra agent inheriting the parent model. It confirmed limits concerning physical inconsistency of fixed snapshots and avoiding overstatement of additional ADC completions as an app loop. Separate model-family review and an unavailable transcript archive audit are not claimed complete.
