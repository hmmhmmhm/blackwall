# Emulator Workflow and Progress Recheck — bw365

2026-11-14. Astra was invoked once, read-only, at the user's request. This reviewed the current objective and saved evidence; it did not execute new firmware, access physical hardware, or publish externally. Do not reuse this request as authorization for later Astra execution.

For UART execution results after bw365, see [bw366 normal RX integration](../hardware/communication/uart-rx-display-mspi0-integration.md). The boundary table below reflects the bw365 review.

## Objective and progress

The active goal confirmed by the parent with get_goal was already a **G2 hardware emulator for CFW testing**. The first scope is a functional verification tool running one temple from original ARM main reset and connecting phone, opposite temple, and case through declared virtual peer contracts. It excludes CFW user-feature development, web-installer productization, physical installation/recovery certification, and full chipset cycle accuracy. Since documentation and Goal match this scope, do not complete or recreate the unfinished Goal.

The old 44.8% is 13/29 in v2. Current v3 confirmed valid saved evidence for E01–E04: **4/16 = 25.0%**. These figures use different scopes and must not be compared as a change. This review does not change the denominator 16, existing acceptance, completion states, or evidence pins.

The exact formula is `100 × number of valid completed acceptance criteria ÷ 16`. Each completed condition adds 6.25 percentage points. One more yields 5/16 = 31.25%; two yield 6/16 = 37.5%. The tool displays one decimal. Effort differs by condition, so this is not an estimate of workload or remaining duration. Reviews, documentation cleanup, and unit-test counts do not raise the numerator.

## Full scope and remaining assessments

This is the complete list of functional areas. Items with undecided inputs/expectations remain incomplete plans and must not be reported as implemented. Detailed acceptance is in [scope criteria](../data/project-scope.json), and existing minimal scenarios are in the [roadmap](emulator-roadmap.md).

| Criterion | Current | Next result needed for completion |
| --- | --- | --- |
| E01 assets/inputs | Complete | Retain provenance, SHA, and incompatible-input rejection evidence |
| E02 original M55 reset | Complete | Retain reset execution and stop reproduction evidence under pinned environment |
| E03 CPU/IRQ/protection | Complete | Retain declared smoke-set evidence; not full ISA certification |
| E04 new candidate registration | Complete | Retain raw candidate inspection evidence in the same runner; not general CFW compatibility completion |
| E05 services/app | Partial | Pin required services and first app event; run three originals from reset → initialization → actual task processing/wait/resume |
| E06 reset/restart | Partial | Pin reset causes and volatile/retained state → virtual device reset → app reentry |
| E07 storage retention | Partial | Pin actual storage objects/ranges → original write → original read after restart and neighbor preservation |
| E08 storage failure | Partial | Pin and verify write/erase failure, interruption, version mismatch inputs and expected damage/restart outcomes |
| E09 natural display | Partial | Legitimate input without test caller → UI → render/submission → 576×288 guest frame and viewer |
| E10 continuous display | Not started | Pin frame count, events, and virtual-time budget → original continuous frame order/content changes |
| E11 device input | Partial | Pin touch/ring/gesture support list → bus/GPIO/IRQ → original consumption → state/UI change |
| E12 sensor samples | Partial | Pin IMU, required auxiliary sensors, and sample formats → FIFO/IRQ → original consumption |
| E13 peer messages | Partial | Pin phone/temple/case roles and messages → transport → original task → app behavior |
| E14 communication failure | Partial | Pin disconnect/delay/error inputs and time limit → timeout/state → reconnect or explicit failure |
| E15 candidate comparison | Partial | Independently assess intended differences and preserved behavior of a new candidate in the same scenario |
| E16 developer tools | Partial | One-command execution/frame/events/interruption/comparison reports, new-environment reproduction, missing assets, and process recovery |

## Current boundaries and next verification gates

| Path | Actually confirmed boundary | Next gate | Relationship to overall score |
| --- | --- | --- | --- |
| Normal natural main | Three originals store 225 bytes bias/GAF → strict stop at first GAF service request 7c000402 | Establish normal service effects/completion and initialization return; no arbitrary ready, branches, or success returns | Not complete before E05 app-event processing and E12 sample consumption |
| UART communication | bw361 callback contract → bw362 original request/parser/free → bw363 actual M55 TX DMA/IRQ and CRC-error return | bw364 RX FIFO → actual IRQ/ISR → original receive task → parser. Native RX not yet verified | Resolves a device-input dependency; full E13 completion is separate |
| API display diagnostic | Original render/submission/IRQ and actual nonzero guest surface; 102-word conversion unsupported | GPU sampling reference policy/conversion → frame wrapper. Policy selection deferred | API checklist 3/6, not natural-main E09 completion |
| Candidates/tools | New candidate input completes E04; multiple diagnostic runners exist | Connect supported scenarios, difference/preservation oracles, and one-command reporting | Simply bundling runners does not complete E15/E16 |

bw361–363 advanced from direct callback/API input to actual transmit transport. Actual RX device input and natural app initialization were not yet connected. Do not count bw364 unit tests as native RX integration success or add API diagnostic success to natural-main boot success.

## Task selection and closure

1. **Close the scope-contract inventory.** Pin inputs, expectations, failure controls, virtual-time budgets, prerequisites, and evidence paths for the 12 incomplete criteria from existing original code and reports. Mark unknown values unknown and gather needed decisions together. Do not arbitrarily drop supported items or promote them to physical-hardware equivalence.
2. **Gate A — finish in-progress UART RX as one integration gate.** Verify FIFO/IRQ through original receive task/parser. Distinguish normal, no input, and bad CRC. If evidence for actual UART receive thresholds/timeouts is missing, leave that point as a blocker; do not manufacture success with fake IRQ, padding, or internal callbacks.
3. **Gate B — connect actual root input and original request production.** After RX, connect virtual phone/touch/root app event → original request production → reply/UI. The current request is produced by an API test caller. Reply 2 approves the previous request's app/payload and does not establish delivery of new UI content. Even with RX results, E05 is incomplete until normal GAF effects and service initialization are resolved. Do not multiply ID/ready/NAK variants converging on the same GAF boundary. Add the next 6.25 points only when a full criterion completes.

Each task result records previous → current boundary, newly enabled behavior, resolved required dependencies, remaining blockers, and next pass conditions. If two consecutive tasks do not change objective causality or required dependencies, switch direction before a third similar probe. Reuse saved audits rather than rerunning completed evidence with identical inputs.

**Gate C**, after normal service and GPU/font contracts, is reset → first event → original UI → full guest frame without a test caller. Do not add A/B diagnostic success together and call it C success. A includes short or fragmented receive, no input, normal input after CRC error, task/stack return, and preservation of the new model's default native path. RX timeout, error frames, and physical time are unsupported in the current unit model.

## Shared scenario groups for remaining contracts

These groups reduce duplicate fixtures without creating a new score. IDs are pinned here as planning identifiers, not evidence of functional passes. The shared profile is one temple main reset plus declared virtual peers, targeting stock24/stock23/Faceclaw38; comparison/CLI also include registered candidates. Each E criterion in each group retains an independent terminal oracle.

| Scenario ID | Criteria | Existing partial evidence | Undecided blocker and next contract investigation |
| --- | --- | --- | --- |
| S-app-peer | E05/E13 | Original request/parser/callback and native TX/CRC | B-root: actual root event and request-production causality. Trace backward from original caller to device input; pin message/payload, completion observation, and time limit |
| S-display-input | E09/E10/E11 | API original draw/guest surface | B-frame: natural frame completion, updates, input types. Use existing frame wrapper/input-consumer source and GPU policy to pin support list, frame count, pixel oracle, and time limit |
| S-sensor | E12 | Through initialization/GAF request | B-sample: sensor sample format, required auxiliary sensors, GAF effects. Use original FIFO consumer and service dependencies to pin samples/IRQ, observations, and time limit |
| S-store-reset | E06/E07 | Existing virtual storage/individual reset model evidence | B-persist: actual app storage items and retained areas. Pin addresses, allowed ranges, and reentry oracle from original write/read/reset calls |
| S-fault | E08/E14 | CRC-error branch and native return | B-fault: expected state after storage interruption and peer disconnect/delay. Pin injection boundary, time limit, damage scope, and recovery/explicit-failure oracle from original error/timeout consumers |
| S-compare-cli | E15/E16 | E04 candidate registration and existing runners/saved audits | B-oracle: intended candidate differences and preservation contract. Reuse scenarios above to pin difference/failure classification, artifacts, reproduction and recovery commands |

Before execution, each group record must include profile, original targets, device input, completion observations, virtual-time limit, negative controls, dependencies, and evidence location. Unknowns in this table were not yet filled in. Defining a group's contract and validating the behavior of its E criteria are separate. Reuse existing normal/failure captures; do not rerun identical group inputs once per criterion.

## Review and verification record

Astra's final review supported retaining denominator 16 and 25%. It found recent bw361–364 work removed real dependencies but noted the request origin was a test caller. The recommendation was adopted to separate first event/original request production and natural full frame after RX into gates B/C, and group undecided contracts into six shared scenarios with concrete blockers. Astra read local docs/source and the bw363 manifest/bw364 unit report; it made no new executions or modifications.

Parent verification: 14 progress-tool regression tests passed. Before/after scope JSON comparison showed only next_steps changed; acceptance/status/evidence for all 16 criteria and current API gates were unchanged. Progress-tool inspection of saved evidence yielded 4/16 = 25.0%. Verification is retained in `private:simulator/emulator-scope-audit-bw365-01/verification.json`. The Goal remains active with its existing emulator-only wording. ALIGNS already matched the objective, so its overall Last aligned was not updated. bw364 remains incomplete. This review itself receives no product completion score.
