# Emulator Scope and Progress Management Recheck — bw376

2026-11-14. This was a one-off Astra direction review requested by the user. It compared the active Goal, scope v3, work records, and saved bw375 results without feature development or a new guest run. The review is not evidence of feature completion.

## Objective and score

The active Goal was already a **G2 hardware emulator and development tools for testing custom firmware**. Run original stock, Faceclaw, and registered candidates from one temple's ARM main reset, and declare virtual phone, opposite temple, and case roles per scenario. CFW user-feature development, productizing a web installer, and physical installation/recovery certification are excluded. Full chipset cycle accuracy and simultaneous original execution of both CPUs and case are not promised.

The current Goal and user request match, so do not complete it or create a new Goal. Preserve ALIGNS and the existing 16 acceptance criteria.

- Current: E01–E04 complete, **4/16 = 25.0%**.
- One more fully satisfied condition: **5/16 = 31.25%** (dashboard 31.2% to one decimal).
- Two more fully satisfied conditions: **6/16 = 37.5%**.
- Each condition is **6.25 percentage points**. This measures acceptance criteria, not effort, duration, or hardware accuracy.
- **44.8% is 13/29 in old v2**. Do not compare or combine it with v3.

## Full scope and remaining work

| Criterion | Current status | Key result still required for completion |
| --- | --- | --- |
| E01 input/identification | Complete | Retain existing asset/model hashes and rejection evidence |
| E02 original execution | Complete | Retain pinned M55 reset execution and stop-reproduction evidence |
| E03 CPU fundamentals | Complete | Retain evidence for declared exceptions, IRQs, and protection set |
| E04 candidate registration | Complete | Retain registration, layout, and execution evidence; candidate behavior comparison is E15 |
| E05 services/app | Partial | Normal GAF service effects, required initialization return, original app event/wait/resume |
| E06 reset | Partial | Volatile/retained state and app reentry after runtime reset |
| E07 storage | Partial | Original write → restart → original read and neighboring-region preservation |
| E08 storage failure | Partial | Damage scope/restart after write/erase failure, interruption, and version mismatch |
| E09 first display | Partial | Natural UI without test caller → draw/submit → 576×288 guest frame and viewer |
| E10 display updates | Not started | Continuous frame order/content/completion for pinned events and virtual time |
| E11 input | Partial | Bus/GPIO/IRQ input → original consumption → state/display change and failure controls |
| E12 sensors | Partial | Samples → FIFO/IRQ → original consumption; required auxiliary-sensor/sample contract |
| E13 peer communication | Partial | Close time limit, peer roles, controls, and evidence package for end-to-end time-setting result |
| E14 communication failure | Partial | Timeout/error/state and reconnect or explicit failure after disconnect, delay, and malformed messages |
| E15 candidate comparison | Partial | Independently assess intended candidate changes and preserved behavior in the same scenario |
| E16 developer tools | Partial | One-command execution, frame/events/failure/comparison reports, reproduction in new environments, and recovery |

Functional scope was identified, but not every detailed input, assessment value, time limit, or remaining effort had been fixed. Do not describe this as “25% of the entire development process complete.” Existing detailed acceptance follows project-scope.json; scenario contracts follow emulator-roadmap.md.

## Current flow and reason for stalled progress

Earlier partial successes accumulated in natural-main device initialization, API rendering diagnostics, and UART/BLE communication research. They are valid partial results but did not satisfy higher-level acceptance, so the score did not change. The auxiliary first-screen checklist 3/6 is also not added to the overall score.

bw371–375 sequentially closed communication gaps. Saved results for three originals reach device connection → GPIO/IRQ → original HCI/ATT → EUS/TPL → actual ble_msgrx → RTC application → consumer-function return. Writing a read-only attribute is rejected with original permission error 3 and does not change RTC. No API caller or forced guest PC/TCB/SP setup is used in this path.

However, bw375 remained in progress: advance pinning of virtual-time budget and closure of phone/opposite-temple/case roles and output scope were outstanding. Do not assume the opposite temple is unnecessary before checking whether a peer synchronization request occurs. Do not extend saved success into completed E05 natural initialization, E09 full display, or E14 failure recovery.

## Review adoption

Astra recommended retaining the v3 goal and 16 criteria, closing E13 independently, fixing time/role contracts first, and reusing scenarios in existing runners. The parent adopted these recommendations. bw371–375 advanced required connections, so there was no evidence to characterize them as wasted repetition. Existing criteria, denominator, and evidence judgments remain unchanged. Limit subsequent execution to this order:

1. **Close E13:** Before execution, record pinned phone/controller inputs, original app endpoint values, and virtual-time budget. Confirm actual opposite-temple/case roles and outbound-sync scope from source and execution state. Assess normal three originals, read-only target rejection, and default-off regression under one contract and save a pinned manifest. Preserve existing successful captures. Record the reason if rerunning due to missing timing measurements.
2. **Communication failure E14:** On the same runner as the completed E13 scenario, add disconnect, delay, malformed-message, cleanup, and recovery assessments. Do not close all E14 based on E13 attribute-permission rejection alone. Pin original per-failure behavior and time budgets first.
3. **Natural services/sensors E05/E12:** Close broken points in GAF computation/completion, initialization return, and actual sample consumption. Do not merely multiply ID/NAK/ready variants at the same strict barrier.
4. **Display/input E09–E11:** Resolve the pending GPU conversion policy, then connect natural UI/full frame, continuous updates, and input effects in the same execution.
5. **Reset/storage E06–E08 and candidate/tools E15–E16:** Fix storage-object, retention, and fault-injection contracts and verify original consumption/restart. Reuse already established scenarios and runners for comparison and shared tools.

This is a recommended work order, not a claim that every criterion depends serially on the others. E13 acceptance does not require E05 completion, so it can be assessed independently when a legitimate reset run reaches original app behavior through device input. Continue to disclose E05's incomplete initialization.

At each task's end record **previous boundary → new boundary / resolved required dependencies / remaining blockers / next pass criterion**. If two consecutive tasks fail to change the boundary, dependencies, or uncertainty, change direction before a third similar probe. Extend scenario contracts in existing runners instead of adding a new script for each function or register.

## Evidence assessment cautions

The first verification of stock24 native-05 failed because it used a connection-only auditor. Do not delete it or overwrite it as successful. A separate phase-aware saved audit of the same capture, `private:simulator/runtime-att-saved-audit-01/stock24/verification.json`, passed 23 checks. Stock23/Faceclaw native-05 saved audits passed. Distinguish execution endpoint values, initial audit failure, and later saved-audit success.

During this review, only completion of already-running bw375 unit tests was collected, confirming 24 passed. No new guest execution or physical-device access occurred. Fourteen progress-tool regression tests passed; before/after scope comparison checks that existing acceptance/status/evidence, denominator, and valid score are unchanged. Detailed verification is in `private:simulator/emulator-scope-audit-bw376-01/verification.json`.
