# Emulator Scope and Next Completion Criteria Recheck — bw370

2026-11-14. This was a one-off Astra review at the user's request. It compares bw366–369 results and the active Goal after bw365. No new firmware execution or device access occurred. Plans in this document are not evidence of feature passes.

## Objective and completion rate

The active Goal was already a **G2 hardware emulator for CFW testing**. It builds developer tools to run original stock, Faceclaw, and registered candidates and compare display, input, sensors, communication, storage, reset, and failure behavior. The first supported profile uses original ARM main reset on one temple and explicit virtual phone, opposite temple, and case. CFW feature development, a web installer, and physical installation/recovery certification are outside the current objective. Full-chipset cycle accuracy and complete original execution of both sides/case are not promised.

Goal and ALIGNS already match this scope; do not complete or recreate the Goal. Retain the 16 [v3 acceptance criteria](../data/project-scope.json).

`Completion rate = number of criteria with valid completion evidence / 16 × 100`

With E01–E04 complete, the rate was **4/16 = 25.0%**. One additional full pass yields **5/16 = 31.25%**; two yield **6/16 = 37.5%**. Each criterion is 6.25 percentage points, not an estimate of workload or remaining time. The historical 44.8% is 13/29 from prior v2. Partial implementation, new tests, and this review do not receive an overall score.

## Current execution boundaries

| Path | Verified result | Still needed |
| --- | --- | --- |
| Natural main | 225-byte GAF configuration and first service request for three originals | Normal service effects, initialization return, actual app event |
| UART receive | Virtual RX → IRQ/receive task/parser → UI delivery, pending release, and return | Short frames/timeouts and integration with actual request origin |
| Request generation | TPL API input → original queue → UART task ID/frame/DMA → caller return | Replace test caller with virtual device input |
| BLE upper-layer input | EUS/ATT registration, permissions, lookup, and isolated Faceclaw wrapper execution | Original stack connection-state creation and normal ATT delivery |
| Display | Original draw/guest surface in API diagnostics | Full-frame conversion and natural UI without test caller |

All 41 scenarios in the bw369 frozen report matched source04 byte-for-byte. The current snapshot's DM connection slot is inactive and the original ATT dispatcher returns before EUS delivery. This is not evidence of a successful normal connection. The existing EM9305 peer has no runtime-event injection API. Host-filling connection/security bytes is not accepted as integration success.

## Complete remaining scope

| Criterion | Minimum result for completion | Dependencies / undecided contracts |
| --- | --- | --- |
| E05 services/app | Three original resets → required initialization → original task app-event processing and wait/resume | Normal GAF service and actual event origin |
| E06 reset | Virtual device reset → retained/volatile state verification → app reentry | E05, reset cause and retention scope |
| E07 storage | Original write → restart → original read and neighbor preservation | Storage items/ranges and restart oracle |
| E08 storage failure | Damage/restart assessment after write/erase failure, interruption, and version mismatch | E07, injection points and failure expectations |
| E09 display | Legitimate initialization/input → UI/draw/submit → 576×288 guest frame and viewer | E05, GPU conversion/reference policy and frame provenance |
| E10 updates | Original continuous frame order, content changes, and completion/wait | E09, events, frame count, and virtual-time budget |
| E11 input | Bus/GPIO/IRQ input → original consumption → state/UI change | Input types, controls, and E05/E09 integration |
| E12 sensors | Samples → FIFO/IRQ → original consumption result | GAF/required auxiliary sensors and sample format |
| E13 peer communication | Declared peer role → transport → original protocol/task → app behavior | Actual root input, per-peer message/completion oracles |
| E14 communication failure | Disconnect/delay/malformed message → timeout/error/state → reconnect or explicit failure | E13, time limit and recovery expectations |
| E15 candidate comparison | Assess intended candidate differences and preserved behavior in the same scenario | E04, scenarios, and independent oracle |
| E16 developer tools | One-command execution, frame/events, failure/comparison reports, new-environment reproduction, and recovery | Supported scenarios, E15, and missing-asset guidance |

This is a functional scope list. Some detailed inputs and time budgets are undecided, so do not claim total effort or completion date is fixed. Preserve the six shared scenario groups in [bw365](emulator-scope-audit-bw365.md) and do not repeat the same execution for each condition.

## Review adoption and next work

Astra recommended retaining the goal, denominator, and 25%, and first establishing executable contracts for incomplete criteria. The parent reread the root contract and native request document and confirmed that **TPL app0b data requests differ from display app010b and bw368's UI queue is 0**. `01020304` is a distinguishing transmission input, not a validated app payload. Do not report distinct bw366 and bw368 executions as a single end-to-end path. ATT research is a candidate E13 path, not established as the project's only critical path.

The next completion candidate was **E13**. App endpoint, valid payload, and time limit were not yet fixed, so close it in this order:

1. **App endpoint contract:** Find one valid message in an existing service handler and an observable original-app state change. Pin input, assessment values, failure controls, virtual-time limit, three-original scope, per-peer roles/reasons for inactivity, and evidence paths before execution. Do not lower app behavior to queue growth alone. If display is the endpoint, data → service → display causality is also required.
2. **Feasibility:** Check whether the selected event can legitimately be scheduled before the current GAF strict barrier. If blocked, retain E13 linkage as partial evidence and switch to E05 normal service effects/completion. Do not bypass with an API caller to claim completion.
3. **Minimal connection contract:** Connect only required controller connection-complete event, readiness/IRQ, and original HCI/WSF/DM path. Original code must create the CCB. Do not add unrequested MTU expansion, bonding, encryption, or multiple connections.
4. **End-to-end validation in one execution:** Connect virtual device ATT → EUS/TPL → original task → selected service handler → app assessment values. Construct any necessary peer reply from request ID/payload in the same run. After normal/no-connection/malformed controls for three originals, cleanup/wait, and saved audit, assess the complete existing E13 acceptance.

If the first investigation cannot establish a valid app payload/assessment value, switch to handler research instead of expanding controller functionality. If a CCB is created but not connected to the app, investigate that app boundary instead of adding BLE features. If two consecutive tasks neither remove required dependencies nor determine feasibility for the chosen scenario, reassess direction before a third similar probe. Add the next 6.25 percentage points only when a full criterion passes.

E13's old next_action (RX connection planned) was corrected to fixing the current app endpoint contract. All 16 acceptance/status/evidence criteria and API checklist 3/6 remain unchanged. Besides overall fulfillment, the dashboard's next_steps show the next completion candidate, undecided contract, recent execution boundary, and current blocker. Do not create a separate estimated percentage.

## Verification and limitations

Astra performed only a one-off read-only review. The parent confirmed that all 41 saved bw369 frozen-report scenarios passed and matched source04 bytes. Fourteen progress-tool regression tests passed. Scope before/after comparison and valid-completion-evidence checks are retained in `private:simulator/emulator-scope-audit-bw370-01/verification.json`. Only local plans/records were changed, without new guest execution, device access, or GitHub publication. bw369 has behavioral research results but still lacked its existing task-closure record, which is distinct from completion of this review.
