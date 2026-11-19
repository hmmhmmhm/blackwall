# Emulator Scope and Execution Flow Recheck — bw359

At the user's request, gpt-6-astra was invoked once, read-only. The parent directly checked the active Goal, scope v3, and current progress tools, and read and applied project-local alignment. This was a scope/workflow review: no new firmware execution, model changes, hardware access, or external publication. Do not reuse it as authorization for a later Astra invocation.

## Conclusion and Goal

The active Goal was already a G2 hardware emulator for CFW testing and matched the user request. It was not marked complete or recreated. The objective is a functional verification tool that executes original stock 2.4/2.3, Faceclaw, and registered candidates from one temple's main reset and reproduces/compares display, input, sensors, communication, storage, reset, and failure with declared virtual phone/opposite temple/case peers. CFW user-feature development, web-installer productization, and physical installation/recovery certification are excluded. Full-chipset cycle accuracy or complete original execution of both sides/case is not promised.

No major missing functional area was found among E01–E16. However, some test inputs and expected values below remain undecided. Having a scope of all areas differs from having every implementation task and its effort fixed. Fixing undecided contracts is part of remaining work.

## Progress formula and advancement

Use `100 × valid completed acceptance criteria / 16`. Do not count a done label alone: inspect specified evidence files, hashes, and assessment values. E01–04 were valid: **4/16 = 25.0%**. Fully verifying one condition adds 6.25 percentage points. The next yields 5/16 = 31.25% (31.2% at one decimal in the tool). This is not an estimate of effort, schedule, or physical accuracy.

The old 44.8% is 13/29 in v2 and uses a different denominator. Do not describe the new denominator as increased progress. The API first-screen checklist 3/6 is not added to the overall number and is not natural-boot completion. This management/review work receives no completion score.

## Full remaining scope and completion evidence

Each row specifies work to turn existing acceptance into execution tests. Undecided items must be pinned from source and existing evidence; this table does not mean implementation is complete. Normal/error controls use the same board, model, and observation policy, with profile differences noted.

| Criterion | Current | Evidence to pin or obtain next | Dependencies / failure controls |
| --- | --- | --- | --- |
| E01 inputs/assets | Complete | Retain existing hash/provenance/incompatible-input rejection evidence | Check new-profile assets separately |
| E02 original M55 reset | Complete | Retain pinned reset execution/stop reproduction evidence | Distinguish from app startup or ROM cold-boot completion |
| E03 CPU/IRQ/protection | Complete | Retain evidence for declared smoke set | Not full M55 ISA/physical-time certification |
| E04 candidate registration | Complete | Declared raw candidate/vector/extent/anchor checks and same runner | Not general ABI compatibility of arbitrary recompiled candidates |
| E05 services/app | Partial | Pin required services, first app event, processing-complete observations, and allowed errors; run three originals reset → normal initialization → task processing/wait/resume | GAF effects and actual producer undecided. Exclude forced branch/return/TCB; error progress cannot replace normal success |
| E06 reset | Partial | Reset type, volatile/retained regions, expected app reentry | E05-based execution; distinguish from host PC reset |
| E07 storage | Partial | Original-written items, addresses, allowed ranges → original consumption after restart | E05/06, neighboring regions and input original unchanged |
| E08 storage failure | Partial | Write/erase failure, interruption points, data/version mismatch expectations | E07; distinguish damage scope, explicit failure, and recovery |
| E09 natural display | Partial | Chosen GPU/font contract, frame completion, actual 576×288 guest frame/viewer from natural input | E05 and device/transport producer; no-input/wrong-input controls; do not count synthetic caller as integrated evidence |
| E10 continuous frames | Not started | Frame count, events, virtual-time budget, order/pixel changes | E09; detect frozen frame/submission without completion |
| E11 input | Partial | Touch/ring/gesture support list and bus/GPIO/IRQ → original consumption → UI expectations | E05/09, no-input/wrong/duplicate controls; do not automatically narrow scope to touch |
| E12 sensors | Partial | IMU/required auxiliary sensors and sample formats → FIFO/IRQ → actual consumption | E05 and device contracts; empty FIFO, IRQ deassertion, unsupported access |
| E13 peer messages | Partial | Phone/temple/case roles and message ID/payload → transport → original task/app | E05 and producer contract; wrong target/unsupported messages |
| E14 communication failure | Partial | Disconnect/delay limits/error payload → timeout/state → reconnect or explicit failure | E13; unconditional ready/ack prohibited |
| E15 candidate comparison | Partial | Intended candidate difference/preserved-behavior oracle and same-scenario comparison | E04 and target behavior; distinguish model unsupported/fixture differences from regressions |
| E16 developer tools | Partial | Execution environment, one-command frame/events/stop/comparison reports, new-environment reproduction | Reuse runners, missing-asset guidance and stopped-process recovery |

## Current execution boundaries

- Normal canonical bw353 for three originals: explicit GAF/trim input → 225-byte bias/GAF storage → strict stop at first service request `7c000402`. EDMP calculation and completion are unknown.
- bw354: 132 original-helper scenarios use isolated M7/synthetic I/O. A subsequent write after timeout is not normal service success.
- bw358: an explicit initial-ready/ID-mismatch virtual profile also converges on the same first GAF service. Initial driver error and subsequent local state were distinguished. Physical power-on state, upper initialization return, and app startup were not validated.
- API display diagnostic: partial evidence through original draw/IRQ/actual nonzero guest surface. Sampling/nibble/quantization of the next 102-word conversion was unverified. Do not automatically apply the GPU reference policy awaiting approval.

## Next three tasks and closure criteria

1. **Pin current status and acceptance scenarios.** Remove guidance naming already completed bias/clock/setter and E04 as next tasks and the outdated current 3/16 notice. Leave unknown inputs, expectations, failure controls, dependencies, and evidence paths as shown above. This management task does not increase the score.
2. **Assess actual bus error → upper return → app producer relationship.** Distinguish NAK from WHOAMI mismatch and missing-peer IllegalCommand; first inspect actual IOM state/original HAL contracts. Connect to natural M55 only with evidence. Distinguish lower error, initializer/wrapper return, task/queue changes, and app event. Stop after obtaining an answer or identifying required unsupported behavior. If it reconverges on the same unknown GAF service, defer that path instead of multiplying identity/ready variants. Wrapper 0, a subsequent write, or progress after NAK does not grant E05 success.
3. **Connect legitimate device/transport producer.** Connect the existing API producer to actual touch or a declared peer message and pin no-input/wrong-input controls. If normal execution is blocked by GAF, complete only producer-contract analysis and retain E05/E09 status. E15/E16 comparison/report contracts can be prepared independently, but do not award points early.

If evidence for normal GAF calculation cannot be found, state that limitation. Do not supply only ready and pretend the algorithm succeeded. With GPU reference-policy approval, restrict GPU work to the existing conversion buffer → IRQ → waiter → frame wrapper scope, then return to natural-input paths.

Before each task, record which **required dependency** of which acceptance condition it resolves and when each result means continue, defer, or switch. If two consecutive tasks do not change target causality or a required dependency, switch before a third similar probe. A single new register value or increased test count alone does not justify continuation. If the current model rejects a legitimate reread/order difference in new CFW, report a support-contract limit; do not disable all guards.

## Adoption and verification

The parent updated current scope next_steps, E05/E12/E16 guidance, and stale current-boundary text in the roadmap and catalog. Acceptance, completion status, evidence pins, denominator 16, and API checklist were not changed. The parent directly confirmed the active Goal already matched the request. Since ALIGNS' existing objective also matched, the overall alignment approval time was not changed.

Fourteen progress-management regression tests passed. Before/after checks confirmed IDs/titles/groups/acceptance/status/evidence of all 16 conditions and API gates remained unchanged. Progress-tool inspection of existing evidence yielded 4/16 = 25.0%. This is saved-evidence inspection, not a new native run or physical validation. Astra likewise performed only read-only comparison of documentation, source, and saved manifests.
