# Emulator Workflow and Completion Criteria Recheck — bw380

This was a one-off, read-only Astra review at the user's request. It compared the active Goal, ALIGNS, scope v3, current code, and retained evidence. No new guest execution, physical-device access, CFW feature development, or external publication occurred. The review itself is not a product completion criterion.

## Active objective

The deliverable is a **G2 hardware emulator and development tools for testing custom firmware**. Execute actual ARM main from stock, Faceclaw, and registered candidates from one temple reset; support phone, opposite temple, and case through virtual peer contracts declared in scenarios. CFW user features, web installer, and physical installation/recovery certification are outside this goal. Do not promise full chipset cycle accuracy or simultaneous original CPU/case execution on both sides.

The active Goal and scope already cover this. Do not mark the goal complete or create a duplicate Goal. Preserve the existing 16 acceptance/status/evidence criteria.

## Progress and advancement conditions

- Valid completion: E01, E02, E03, E04, E13, **5/16 = 31.25%**. The dashboard displays 31.2% to one decimal.
- Remaining: **11 conditions**. One more complete pass yields **6/16 = 37.5%**; two yield **7/16 = 43.75%**.
- Each condition is worth 6.25 percentage points. Do not increase the score for partial tests, documentation, or task counts. This does not mean equal effort per condition or estimate remaining time.
- The old **44.8% = 13/29 in v2** belongs to a previous product scope. Do not compare it as an increase/decrease against the current score.
- The first-screen checklist including API diagnostics, **3/6**, is separate. Do not add it to natural boot or overall emulator completion.

## Complete scope

| Criterion | Status | Remaining end-to-end assessment |
| --- | --- | --- |
| E01–E04 execution foundation | Four complete | Retain evidence of pinned inputs, reset reproduction, CPU fundamentals, and new candidate registration |
| E05 service/app lifecycle | Partial | Verify required initialization → original app event → wait/resume without forced branches/TCB changes |
| E06 reset | Partial | Device reset during execution → volatile/retained state → original app reentry |
| E07 storage retention | Partial | Original write → restart → original read and neighboring-region preservation |
| E08 storage failure | Partial | Damage scope and restart after write/erase failure, interruption, and version mismatch |
| E09 natural display | Partial | UI without test caller → render → submission → guest 576×288 and viewer |
| E10 continuous display | Not started | Predeclared events/time → continuous frame order/content/completion/wait |
| E11 device input | Partial | Supported input bus/GPIO/IRQ → original consumption → state/UI change |
| E12 sensor samples | Partial | Supported sensor samples → FIFO/IRQ → original consumption; configuration queries alone do not pass |
| E13 peer communication | Complete | Device input for local time setting → actual app/RTC consumption; not complete peer delivery |
| E14 communication failure | Partial | Disconnect/delay/malformed message → timeout/error/state → reconnect or explicit failure |
| E15 stock/candidate comparison | Partial | Distinguish intended differences, preserved behavior, and regressions with identical model/input/time |
| E16 developer tools | Partial | One-command execution/scenarios/frames/events/comparison, new environments, missing assets, and interrupted-run recovery |

The supported touch/ring input list for E11, required auxiliary sensors for E12, and reset types/storage objects/failure inputs for E06–08 still need detailed contracts. The 16 criteria are the complete list of functional acceptance conditions, not proof that all peripheral implementation effort or remaining work is already known. Before starting, pin inputs, expected values, time budgets, and failure controls from existing source and evidence. Do not narrow them afterward to easy-to-pass inputs.

## Astra's assessment of the current flow

The direction fits the emulator objective. Recent delay included integration debt: the runtime runner could not reuse already verified GAF components. bw378 connected them and moved the execution boundary from a previous stop at about 1.23 ms to an actual GAF request at about 171 ms. This advances the execution boundary; it is not normal boot completion.

bw379 observed actual requests, RMW, and trigger/pending in an optional control model. Code values `CalculationSupported=false`, `CompletedCalculations=0`, and rejection of unsupported A297 results explicitly show computation is not implemented. Some control checkpoints passed, but the long native result is false and final saved audit/manifest closure is still absent. Keep bw379 in progress; do not promote it as evidence of a complete overall criterion. See [partial observations and limits](../hardware/sensors-input/gaf-on-demand-control-capabilities.md).

Completion points advance slowly because many small analysis/control checks share a common dependency, while full criteria require initialization, consumption, and return. The solution is not reduced acceptance or arbitrary partial scores, but reuse of existing components, verification through the actual consumer, and stopping repetition without evidence.

## Next three verification units

| Order | Deliverable and pass criterion | Blocker or switch criterion | Score effect |
| --- | --- | --- | --- |
| 1. Determine reproducibility of GAF effects | Reuse existing request 2/4 and complete setter/helper evidence to pin a table of driver-read addresses, widths, value provenance, idle/errors, and side effects. Separate supportable effects from unsupported calculations and decide whether bw379 audit can close | If evidence is missing, stop at unknown and identify needed algorithms/code/material. Do not pass with ready/zero results or a longer timer. If two consecutive tasks hit the same causal boundary, change approach before a third similar probe | 0 percentage points for analysis/control closure alone |
| 2. Connect common services and app lifecycle | After implementing evidenced effects, verify original three main resets → required initialization → actual app event → wait/resume in one run. Pin error controls, profile, and virtual time budget before execution | If stopped before initialization/result consumption, keep E05 partial. Do not substitute UI caller or branch/return/TCB seeds. If GAF remains unresolved, switch to common execution/comparison of existing E13 scenario and E04 candidate registration (E15/E16) without claiming integration success | Only full E05 pass yields 37.5% |
| 3. Connect long peer failures to the same runner | Reuse immediate disconnect/CRC/1 ms evidence. Assess delay/loss and original timeout/error/state plus subsequent normal input/reconnection or explicit failure against predeclared oracles | If another guard such as GAF blocks before scheduled input, timeout validation fails. Return to prerequisites rather than multiplying variants of the same delay | Full E14 pass adds 6.25 points; if E05 is also complete, 43.75% |

Starting or finishing each unit is separate from acceptance completion. Determining GAF cannot be supported is useful but is not E05 or Goal completion. The current runtime runner's `--case` accepts only three research images, while the `--firmware-manifest` path for E04-registered candidates exists in a separate runner. If GAF evidence is insufficient, connecting these paths while preserving existing model/input/time is an independent next task. Do not complete E15 based only on markers or the same stop location, and leave E16 partial without frames and other required outputs. Then connect natural UI/continuous frames, input/sensors, and reset/storage using the same pinned scenario basis.

## Work records and duplicate prevention

Before each task, check existing task keys, input fingerprints, and evidence. Record previous → current execution boundary, resolved required dependencies, unsupported points, and the next pass/fail decision. Audit retained evidence with pinned tools instead of rerunning it on a new model. Do not repeat the same input without a revalidation reason when there is no new behavior, branch, or causal judgment.

This review is checked through scope-invariance comparison and 14 progress-management tests. Product completion remains 5/16 and the Goal active. It authorizes no GitHub publication or hardware operation.
