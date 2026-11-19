# CPU Normal-Sleep Model and Natural Execution After WFI

bw-0312. Connected CPUPWRCTRL reads, CPDLPSTATE storage, and APB flush from the [original contract](cpu-normal-sleep-contract.md) as an optional model. Three original binaries advanced past WFI through MSPI0 reactivation and PIO transfer preparation. **Overall acceptance remained 13/29 = 44.8%, scope v2.** This is not assessed as completed full boot or integrated display.

## Changes and limits

Added `BlackwallCpuNormalSleep` to common core source, unselected by default.

- CPUPWRCTRL supplies explicit source-reset read value 0; writes are not permitted.
- CPDLPSTATE stores only existing initial/restore value 0 and verified normal-sleep value `0x11`. Other SDK values such as `0x21` and arbitrary power modes are blocked.
- Flush supplies return value 0 from a declared synchronous bus fixture only after checking original PC, R0=`0x47ff0000`, and readiness. It does not implement physical APB latency or every asynchronous transaction order.
- Repeated flush without a control read in the new normal-sleep cycle is rejected. SCR handling remains with the existing M55.
- No hook changes WFI, branches, or return values. Actual waiting and IRQ dispatch use existing Renode M55 execution.

Instead of adding a new mapping, flush is accessed through the existing strict tail guard. The PPB guard references the same CPU-state owner. The default control does not select this connection. Only core model source changed; the other eight remained unchanged.

## Natural execution results

| Input | Power-control reads / flushes | CPDLP reads / writes / final value | New stop PC |
| --- | --- | --- | --- |
| Stock 2.4 | 2 / 2 | 4 / 5 / 0 | `0x4e8a3e` |
| Stock 2.3 | 1 / 1 | 3 / 3 / 0 | `0x4db66a` |
| Faceclaw 38 | 1 / 1 | 3 / 3 / 0 | `0x4db66a` |

Readiness/flush counts are observed per firmware; identical timing was not forced. CPDLP final value 0 matches the original restore write after WFI. The corresponding late-store literal in the binary was also confirmed as `0xe001e300`. This is **evidence that post-WFI code executed**, not proof of actual wait duration, which IRQ woke it, or successful physical sleep. No additional WFI-ignore setting was added to runner/runtime.

MSPI0 was on in all three inputs, with two on requests, three responses, one off cycle, and one controller reset. Clock was reenabled, CQCFG=2, software flags=`0x80`. In original SRAM, retention-valid marker changed from prior 1 → current 0, and enabled handle `0x3bebebe` was confirmed. The model does not directly modify guest SRAM.

The new boundary is original `str.w r7,[r2,#0x208]` writing `0xffffffff` to `MSPI0.INTCLR(0x40060208)`. Existing strict mask checks blocked this clear-all operation. The original then prepares PIO control, so next analyze IRQ clear-all together with PIO command, buffer, status, and completion conditions. Panel transfer and framebuffer generation had not succeeded.

Prior BLE 59 commands/60 responses and event prefix remained. Default unselected control CPU, instruction count, full observed state, and selected events exactly matched the earlier CPUPWRCTRL-blocked state.

## Verification and preserved failures

- Tools: `prepare_cpu_sleep_candidate.py`, `verify_cpu_normal_sleep.py`, `inspect_cpu_sleep_profiles.py`.
- Passed 22 new unit, 22 frozen, 24 existing MSPI0 retention, and 33 config checks. Verified rejection of incorrect values, PCs, addresses, order, and repeated flush, plus state preservation.
- Performed four valid native main runs (three originals and one default control) and four saved re-audits. Contrary to initial bounded-capture and final CPDLP `0x11` expectations, original execution reached restore value 0 and a new strict boundary. Preserved three initial semantic failures and passed separate saved audits matching actual original writes and boundaries. CPU was not rerun for re-audit.
- The initial board registered a flush address already owned by a strict guard and was rejected at creation. Preserved the original failure and added an existing-guard-owner check to the candidate builder. It was not counted as successful guest execution.
- Froze 91 Python dependencies; saved analysis 01/frozen 02 reports and inspectors respectively match byte for byte. Proprietary main/SRAM, fixtures, and logs remain outside Git at `simulator/cpu-sleep-main-02/`, `cpu-sleep-control-01/`, and `cpu-sleep-saved-audit-01/`. Model, pinned source, and analysis values are in `cpu-sleep-peer-verification-01/manifest.json`.

There was no physical glasses/case connection, flash, OTA, persistent write, external publication, or commit. Full app loop, complete CPU sleep/wake, IRQ cause, and panel output remain unverified. Next investigate original MSPI0 blocking PIO flow and first panel-packet contract; the web installation, Faceclaw CFW, and recovery boot goals also remain.
