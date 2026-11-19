# G2 Functional Emulator v3 Final Audit

bw490. The subject is the 16 existing conditions in `project-scope.json` v3. Neither denominator nor acceptance wording is changed. Physical installation/recovery certification, CFW product-feature development, and complete chipset-accuracy reproduction are outside this completion assessment.

## Requirements compared with actual evidence

| Criterion | Verification and evidence | Assessment boundary |
| --- | --- | --- |
| E01 | Rechecked pinned originals, models, provenance, and actual file hashes; [asset audit](../research/offline-asset-revalidation.md) | Does not obtain every profile or a normal font bank |
| E02 | Reproduced pinned Renode M55 original reset execution and stop | Not cold boot from ROM |
| E03 | Some MVE, exception, and IRQ smoke tests plus memory protection | Not full ISA, security, or cycle certification |
| E04 | [New candidate registration](../firmware/firmware-candidate-registration.md) with independent SHA, size, vectors, and profile, plus rejection checks | Not arbitrary firmware ABI compatibility certification |
| E05 | Three original main resets → services → app events and empty-queue wait/resume on the same task; reran [boot audit](../firmware/native-main-boot-acceptance.md) | Pinned 100 ms post-screen scenario, not long-term stability |
| E06 | Virtual NVIC reset of active device → original reinitialization → UI return; reran [reset audit](../hardware/power/active-board-reset-acceptance.md) | Not every non-idle combination |
| E07 | Original ARM virtual storage write, new-process read, and neighbor preservation | Not physical MRAM/NOR writes |
| E08 | Reaudited [13 pinned failure/interruption/mismatch cases](../research/storage-failure-acceptance.md) | Damage classification is not called successful recovery of all data |
| E09 | Natural main UI/font/submission → guest 576×288; actual PNG also checked | Reference GPU and functional sensor models, not physical pixel accuracy |
| E10 | Continuous frames, content changes, and wait/resume after display for three originals | Not evidence of physical FPS or six-second stability |
| E11 | Reaudited original consumption/display and no-input controls for [touch scroll and ring relay](../research/input-acceptance.md) | Direct R1 BLE and arbitrary gestures unsupported |
| E12 | Reaudited [FIFO/IRQ → sensor_hub](../hardware/sensors-input/sensor-task-consumption.md), numeric ring 2252 bytes, ARM codec 80 bytes, and no-input controls | Numerical GAF/EDMP fusion and physical accuracy unverified |
| E13 | Virtual phone ATT → original BLE/task → RTC commit; checked roles, time budget, permission negative, and file pins | Opposite-temple outbound consumption and case runtime unverified |
| E14 | Reaudited [nine pinned peer failure/recovery cases](runtime-peer-failure-contract.md) | Not all connection errors or full app recovery |
| E15 | Compared three originals/registered candidates under the same model, separating intended changes, actual regressions, and model differences | API diagnostic, not full candidate compatibility in natural main |
| E16 | Pinned new-environment evidence, missing-asset guidance, interrupted-work recovery, actual current CLI execution/comparison, and boundary tests | Separate venv/private root on the same Mac; not certification on other OSes |

Audit commands for E05/E06/E11/E12/E08/E14 were rerun on saved actual captures. Pinned SHA values for all 16 criteria and manifest child files were also compared. This does not claim all past native scenarios were newly executed. Historical semantic audits retain their then-current source/model and are not regenerated with the latest builder.

## Actual candidate comparison with current code

The GPU model changed after bw438, so preflight against an old baseline was rejected. Running the latest original/candidate under the same model matched pixel and complete SRAM expectations but differed from the old trace hash. That failure was retained. Current traces of original and candidate themselves matched.

Existing pixel/SRAM expectations were preserved, and a new expectation file pinned the rule that **the trace must match the current original baseline**. A new candidate run then verified it. There was one baseline run, one failed comparison against the old trace expectation, and one new predeclared-expectation check. Two additional preflight failures did not execute ARM. There were three native runs total, and termination of all owned containers was confirmed.

The final CLI exited 0; candidate execution, semantic checks, and comparison all passed. It confirmed the intended 684-byte screen/SRAM change, preservation of three initial SRAM regions, and matching observed traces between original and candidate. [Current commands and expectation preparation](../research/current-model-comparison.md) were documented and an outdated incomplete statement in the README corrected.

The API scenario's rejection of unsupported GPU textures remains disclosed. Do not mix this with the zero-fault result from the natural-screen test. This was not an audit that overwrote the failed historical trace expectation with candidate results.

## Reproduction and assessment records

Audit logs, reports, frozen tools, and final file manifest are outside Git in `simulator/final-completion-audit-bw490/`. The current CLI capture is in `development-bootstrap-bw438-01/workspace/final-audit-bw490/`. Proprietary images, SRAM, and frames are not added to the repository.

Relevant boundary tests include nine candidate-registration, 13 native semantic-contract, 14 progress-management, two CLI candidate, and four CLI dependency/guidance tests. Failure due to missing packages in system Python was retained, then reverified in the designated venv. Do not claim every test suite ran.

The final machine assessment follows private `final-completion-audit-bw490/report.json`. The 100% in this document or the dashboard alone does not guarantee physical safety or unsupported functionality. Later new features, models, and time ranges require separate acceptance criteria and evidence.
