# Emulator-Only Goal and One-Off Astra Reviews

Current figures follow the [generated dashboard](../project-dashboard.md). The bw342 1/6 and bw343 2/6 figures below are historical baselines. Evidence of the later bw345 renderer call is in [JBD status transactions](../hardware/display-gpu/jbd-display-status-and-render-task.md).

Task bw-0342, 2026-11-13. The user requested that the former CFW-development-focused goal be limited to a **glasses hardware emulator for CFW testing**, with full scope and progress redefined first. A one-off `gpt-6-astra` read-only review was performed. Do not reuse this approval for subsequent Astra execution.

## Review conclusions and adoption

Continue executing actual original ARM code on Renode M55. Change development units from “next unsupported address” to “behavior a developer can test.” Analyze unsupported addresses when they are dependencies needed for that behavior.

The old 44.8% was not a calculation error: it was 13/29 completed criteria under the old scope, combining 18 recovery/web-install/CFW criteria with 11 simulator/tool criteria. Many recent tasks accumulated as partial evidence for large S6/D3 criteria without raising the overall figure. Even 336 completed tasks are not a product-completion rate.

Also correct the separation between latest support and the first documentation guidance. Mark the existing simulator-scope CPU M4 table and usage's initial WIC profile as historical; prioritize the [capability catalog](emulator-capability-catalog.md) and [roadmap](emulator-roadmap.md) for current status. Group hundreds of existing tools into product entry points rather than rewriting them.

The registration and comparison flow for new CFW candidates was included in completion criteria. Running only the existing three images does not complete a CFW testing tool. The pinned research-input limitations in `pinned_main.py` and `firmware_runner.py` need expansion through safe profile registration in E04.

## Active-goal boundary

The objective is a functional-verification virtual G2 and development tools that run original stock, Faceclaw, and new CFW candidates, and reproduce/compare display, input, sensors, communication, storage, reset, and failure behavior. The first supported profile is one temple running from actual main reset with declared virtual phone/opposite temple/case peers. Declare required peer behavior, disconnects, and unsupported states as contracts.

CFW feature development, web-installer productization, and physical installation/recovery certification were excluded from active scope. Existing code is not deleted. Full actual ROM → bootloader → main boot, original binary execution on both CPUs/case, and complete OTA are separate extension profiles. Virtual storage, restart, and interrupted-write verification remain in the baseline 16 criteria. Cycle, analog, RF, power-consumption, and full GPU ISA accuracy are not v1 completion claims.

The first functional-verification scope was applied based on the user's latest scope instruction and existing actual ARM execution requirement. A detailed fidelity-choice question was sent, but no separate answer requesting full-chipset timing reproduction had been received. If such an answer arrives, review it as a new scope version rather than silently changing the denominator.

## Progress and baseline at the time

All conditions were pinned as E01–E16 in [project-scope.json](../data/project-scope.json). Previously completed small areas were not split further to add points.

- E01: input/model identification, hashes, and rejection of incompatible inputs.
- E02: reproduce original M55 reset execution and stop in a pinned environment.
- E03: declared foundational exception, IRQ, and memory-protection set.
- E04–E16: new CFW registration, services/app, reset, storage/failure, full display/updates, input/sensors, peer communication/failure, comparison, and developer execution flow.

Astra proposed E01–03 as reuse candidates and stated it had not itself reverified private hashes. Parent work directly checked existing assessments and artifact hashes, audit pins for the latest three original captures, and 11 models. Unit tests for input environment 3, semantic contract 13, memory export 4, and progress tool 13 also passed. No new firmware execution or hardware access occurred.

The new baseline was **3/16 = 18.75%**, displayed as 18.8% to one decimal. Each completed acceptance criterion adds **6.25 percentage points**. This is a criterion-fulfillment rate, not an estimate of effort, time, or physical accuracy. Do not compare its increase/decrease with v2's 44.8%. The [v2 original](../data/project-scope-v2.json) was retained.

Separately, six steps from “original main reset to first display” were pinned. At the bw342 review, only M1 was satisfied: **1/6 = 16.7%**. This score is not added to the overall numerator. There were static clues for M2's indirect table call, but execution and causality were incomplete, so it was not counted complete. Do not increase the denominator for every newly found function.

## Avoiding repetition and priorities

1. Link currently executable baseline profiles, virtual initial values, unsupported/unknown behavior, and reproduction commands in one place.
2. Follow legitimate display-activation input and preparation helpers to produce the first screen. Do not replace this with sequential zero-filling of 153 IMU initial bytes.
3. If the sensor is an actual prerequisite, organize consumed values, preserved values, and unknowns as one unit. Wrapper return 0 alone does not establish initialization success.
4. Make one device input or phone message change the display through an original task.
5. Connect new CFW registration and stock/candidate comparison in the same scenario.

If two consecutive tasks change none of the current stage, dependencies, or uncertainty, reassess the path before a third similar probe. Continue separating source-only, synthetic caller, natural main, and physical-device evidence. Recognize original M55 draw → submission → diagnostic GPU → guest 64×32 A/W success, but do not promote it to full-main 576×288 success.

Review sources: `docs/data/project-scope-v2.json`, `docs/data/work-log.tsv`, `docs/architecture/simulator-scope.md`, `docs/architecture/simulator-usage.md`, `docs/hardware/display-gpu/nema-live-draw-framebuffer.md`, `docs/hardware/sensors-input/imu-startup-ui-dependency-audit.md`, `docs/hardware/display-gpu/display-queue-producer-contract.md`, `tools/project_progress.py`, `tools/pinned_main.py`, and `tools/firmware_runner.py`.

Parent revalidation is retained outside Git in `simulator/emulator-scope-baseline-01/{review.py,report.json}`. Replacing the existing Goal was initially rejected because one was active. After the user released the existing Goal, `get_goal=null` was confirmed and a new Goal with the scope above registered. The new Goal was active and did not claim emulator completion.

## bw343 one-off Astra recheck

On 2026-11-13, `gpt-6-astra` was invoked once read-only for this new user request. The review used only local documents/source and did not reaudit private evidence, execute firmware, use network, or access physical hardware. Because it confirmed the prior bw342 review and v3 transition, the active Goal was not duplicated or completed. `get_goal` also matched an emulator for original/new CFW testing, 16 criteria, and separate approval for physical access.

Astra's conclusions and adoption:

- Actual ARM execution on Renode M55 and one temple plus explicit virtual peers are appropriate. Keep the Goal and denominator of 16.
- Remove the stale current 1/6 figure from `progress-tracking.md` and refer to the generated dashboard. Mark bw342 figures in this document as historical. Do not edit old ledger rows.
- Specify M2 as an **API diagnostic boundary** and label the auxiliary percentage **first-screen verification checklist (including API diagnostics)**. It includes insertion of a test caller after reset and must not be read as natural-boot completion.
- Actual input/message/expected results for E11–E14 and others were not fully pinned. Add minimal scenarios, failure controls, and undecided inputs for E04–E16 to the roadmap. Items without concrete values cannot be assessed complete.
- Retain the stepwise overall acceptance-fulfillment rate. Each task reports newly enabled behavior, previous → current execution boundary, removed uncertainty, and next pass condition. Do not prioritize only E04 for points.
- The next three integration units are valid content → first draw/submit; device/transport input → natural first screen/updates; and new candidate registration → same-scenario comparison. Storage/reset/sensor/peer failures remain in scope.

Parent work separated current tasks from deferred/failure history in the dashboard generator. Records containing old 44.8% remain in separate history. Related regressions are `tests/test_project_progress.py`: after reproducing and fixing current/history mixing, 14 passed. Evidence reassessment yielded stale 0, overall 3/16 = 18.75% (displayed 18.8%), and checklist 2/6 = 33.3%, with no score change. Actual full main boot and natural 576×288 pixels remained incomplete.

Reviewed files: `AGENTS.md`, `ALIGNS.md`, this document, `project-scope.json`, `project-dashboard.md`, `progress-tracking.md`, `emulator-roadmap.md`, `emulator-capability-catalog.md`, `display-activation-native-diagnostic.md`, and recent `work-log.tsv`. Further Astra execution requires a new user request.

## bw347 one-off Astra review at the GPU submission boundary

At a new explicit user request, `gpt-6-astra` was invoked once read-only. The earlier bw342/343 transition was checked first. Since the active Goal already matched a CFW-testing hardware emulator and scope v3, it was not recreated or completed. This review does not resume firmware feature development or physical-device access.

The review concluded that current direction and the denominator of 16 should remain. Detailed E11–E14 input, sensor, message, and time-budget contracts must be fixed before their implementation, and full GPU ISA or original execution of both sides/case should not be added now. Overall 3/16 = 18.75% and API diagnostic checklist 3/6 = 50% remain. Since final acceptance criteria combine multiple dependencies, the overall score may remain flat for a while and is not an estimate of effort or remaining time.

Changes adopted:

- Correct stale “current 2/6” in scope notes to a bw341 historical record. Preserve the existing ledger.
- Replace the next-task instruction to reinvestigate completed JBD command 05/35 contracts with reuse of existing evidence.
- Expose newly enabled behavior, previous → current boundary, removed uncertainty, and next pass condition in current dashboard guidance. Add no partial score or denominator.
- State natural-main IMU 02ae and API-caller-insertion diagnostic GPU-doorbell boundaries side by side. The latter is not completed natural boot.
- GPU diagnostics verify actual command meaning, DMA ranges, completion/errors, and original waiter resumption. Do not assume the first 24 words are the complete screen command. Then return to natural initialization and device/transport → UI producer integration.

Development speed improvements are to investigate original-function behavioral contracts first and extend existing runners, perform needed controls using the same observation recipe, and reuse stable historical results through saved audits. Continue distinguishing API diagnostics, synthetic, natural-main, and physical evidence. Do not finish E04 first merely to raise the score.

Astra read local documentation and relevant progress-tool/display-diagnostic-runner source. It did not reaudit private hashes or run new firmware. The parent checked 14 progress-tool regression tests, scope JSON structure, and evidence assessments in the generated dashboard. Completion criteria, evidence pins, and score were unchanged. This review did not complete the emulator. Further Astra execution requires a new user request.

## bw348 one-off Astra recheck after quad

At a new explicit user request, `gpt-6-astra` was invoked once read-only. It confirmed current Goal, ALIGNS, and scope v3 already matched a G2 hardware emulator for CFW testing. The objective was not recreated, narrowed, or marked complete. 44.8% is v2 history; at that time acceptance was 3/16 = 18.75% (displayed 18.8%) and the API diagnostic checklist 3/6 = 50%. These are not shares of effort or remaining time.

Astra judged the current 102-word conversion analysis necessary integration work for actual subsequent original submission. It recommended avoiding expansion to the entire GPU, assessing display buffer, original completion/wait, and frame-wrapper results first, then returning to natural-main IMU and device/transport input. Preserving unknown and deferring for insufficient evidence is also a valid conclusion; do not substitute copying expected pixels.

Adoption was minimal. The roadmap M4's outdated statement that submit/pixels were unknown was separated from latest partial evidence, and current/next language at historical checkpoints was grouped as then-current records. Current GPU unit termination boundary and return order to natural main were added. M5/E09 assessment must state GPU profile, reference accuracy, and unsupported/failure controls; do not extend area-reference success into physical MSAA or default strict support. E09 acceptance, evidence pins, and the denominator of 16 remain.

The parent checked active get_goal, the progress tool's current formula, existing E01–03 evidence judgments, and document structure. No new firmware execution, private-capture reaudit, hardware access, or external publication occurred during the review. Existing quad/102-word evidence was reused. The subagent's final opinion and review limitations are summarized here; further Astra execution requires a new user request.
