# One-Time Astra Review of the Current Direction

2026-11-12, bw-0238. At the user's explicit request, one `gpt-6-astra` reviewer was invoked once. This was a read-only review under the project align/ALIGNS criteria; no additional agent, native rerun, or device access was involved. Approval for this review does not authorize subsequent Astra runs.

## Conclusion

Keep original ARM reset execution, strict MMIO, and pinned-input comparisons. Passing the TIMER7 and touch transfers and configuration/GPIO sequence in bw233–237 is real progress. A wholesale engine replacement or weaker guards is not recommended. However, following only initialization frontiers would defer normal boot/display and web installation/recovery integration. Improve the selection of next work and semantic verification first.

## Findings and changes

| Priority | Evidence | Change made |
| --- | --- | --- |
| High P1 | Scope S6 `next_action` named bw155, `next_steps` named bw232, and the top of the plan named UART0. W5/D3 had no next work assigned. | Synchronized S6/D3/W5 `next_action`, dashboard `next_steps`, and the top of the action plan with current evidence, next deliverables, and stopping conditions. |
| High P1 | W5 offline integration is separate from W6, which requires device approval, but had no assignment. Existing installation-flow retains the `installable=false` gate. | Specified the connection contract below and simulator-only transport as subsequent work. The live gate remains closed. |
| Medium P2 | `run_native_candidate.py` can report `passed=true` even when `prefix=false`. Individual private audits supplement semantic verification. | Explicitly distinguished valid execution from passing the behavioral contract. Assigned plan expectations to a subsequent shared-tool change. No claim is made that runner behavior changed during this turn. |

Code review confirmed that the bw237 latch rejects changes to unknown bits and modifies state only after validating the full mask. The reviewer checked saved main3/off and the final 901 checks and found no reason to oppose closing that work. This supports the limited synthetic latch model; reset-zero, immediate touch response, and synthetic initial values are not hardware evidence.

Stock 2.3 and CFW request `0x8e80` and `0xe80`, respectively, even when the next PC/address is the same. Preserve per-input expectations. Do not extend the unresolved cause of 92/66 additional IO observations in the earlier UART trace into a claim of whole-trace equivalence.

## W5 initial integration contract

| Connection | Evidence available for reuse | Next deliverable or gap |
| --- | --- | --- |
| Web file/plan → OTA session | artifact-catalog, installation-flow, ComponentOtaSession, and low-level virtual GATT tests | Simulator-only entrypoint/transport separate from the real gate. Do not make the production catalog installable. |
| OTA packet → virtual storage | Packet/session verification and an existing RAM-backed storage model each exist | Connect component scope, side, completed verification, and commit timing. Keep the two temples' storage independent. |
| Stored image → boot/reset | combined-handoff checks cover only from a pinned hook to immediately before reset | Connect transferred bytes/hash to execution input and integrate the normal reset path. Do not call the existing hook check full boot. |
| Interruption/corruption → reconnect | Single-session failure abort and prohibition of unattended retries | Model state transitions for interrupted writes, corrupted payloads, version mismatch, and reconnecting to the same side, and select a valid image. |
| CFW failure → stock restoration | Stock components, recovery assets, and limited handoff evidence | Connect virtual storage restoration, reset, and execution results. Judge main restoration and full-stock restoration including boot separately. |
| Web UI → complete startup/recovery | Not yet connected | W5 remains incomplete until evidence connects actual ARM main startup through recovery. Physical recovery requires separate W6/R approval and evidence. |

All writes are restricted to separate simulator RAM. Do not invoke the real chooser, BLE, glasses, case, or MRAM. This table defines a connection contract; it is not evidence of completed implementation.

## Next work sequence

1. Structure the common plan's per-input frontier (address/operation/width/value/PC), comparison policy (exact/prefix/subsequence/bounded-invariants), byte/state/IRQ invariants, and allowed/unresolved differences; run host mutation tests. Use it for new native runs and freeze past reports.
2. Investigate the D3 embedded bitmap callback's buffer, release, and actual rendering path within a limited scope. Do not conceal the missing font bank with arbitrary assets.
3. Implement the first offline integration of the simulator-only W5 connections above. Leave normal-boot dependencies incomplete.
4. Investigate S6 IOM6 power → initial transfer → peer boundary using the existing engine. Stop strictly at the first unknown response.

Update the overall goal and remaining dependencies after each operation. Scope v2, product 13/29 = 44.8%, and the completion criteria were unchanged. Display output, full boot, and physical installation/recovery remain incomplete.
