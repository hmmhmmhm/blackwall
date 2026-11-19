# E15 firmware comparison acceptance audit

bw-0436. The scope v3 E15 acceptance wording was not changed:

> Run the new E04 candidate under the same board, input, and timing scenario. Evaluate intended code and display changes separately from boot, input, and communication behavior to be preserved, and distinguish model or fixture differences from firmware regressions.

Fixed display diagnostics and virtual phone input scenarios were compared for each original and new candidate in stock 2.4, stock 2.3, and Faceclaw38. All six pairs passed: three families × two scenarios. E15 is deemed complete. **This is not an acceptance of natural main or the entire UI, and it does not lower the criteria for E05/E09 and others.** E09 separately requires a first screen without a test caller. The E15 comparison scenarios are explicitly limited to API diagnostics.

## Evidence for each acceptance requirement

| Requirement | Actual evidence checked |
|---|---|
| New E04 candidate | Checked distinct SHA, 14-byte extension, original vectors, profile, and registration baseline for each family. Executed with the existing registry and runner without allowlist additions. |
| Same board/input/timing scenario | Model, board, inputs, caller, and observations match within each original/candidate pair; execution Python differs only in main memory length. Fixed timing and stop boundaries were retained. |
| Intended code/display changes | An actual 4-byte BL and appended 14-byte ARM packer set only RGB to 0. For each original and candidate, 24 standalone ARM inputs were checked against the full black surface SHA created before execution and the actual M55 result. |
| Boot preservation | CPU/observations and complete initial, UI, and display SRAM match the original over the declared main reset→initial hold interval and API activation boundary. This is not a completed natural initialization. |
| Input/communication preservation | The same candidate ran virtual GPIO/HCI/ATT→original BLE/app task→RTC commit. The phone path without a PC seed, original stack, app state, queue, RTC, and complete SRAM were preserved. |
| Detection of actual changes/regressions | Each actual display candidate fails with a surface/final SRAM difference under normal original expectations and passes under the predeclared intended-change expectations. The existing actual app_state regression also remains a failure. |
| Distinguish model/fixture differences | Same-condition preflight rejects different model, profile, or input/observation bytes from firmware-only comparison. Historical baselines were not mixed with the current model. |

## Fixed matrix

| Family | Actual display mutation | Phone→RTC preservation with same candidate | Difference detected under normal original expectations |
|---|---|---|---|
| Stock 2.4-based candidate | 20 checks; intended comparison passed | 28 checks; comparison passed | Detected |
| Stock 2.3-based candidate | 20 checks; intended comparison passed | 28 checks; comparison passed | Detected |
| Faceclaw38-based candidate | 20 checks; intended comparison passed | 28 checks; comparison passed | Detected |

All three candidates changed 9 white dots, 684 pixels, from 255→0. Each family's final SRAM otherwise matched except for the 684-byte surface change predicted before execution. Events, samples, hit counts, and activation/display transitions at declared observation points were also preserved. This is evidence about final state and the declared observation range; it does not mean every transient write or PC path was collected.

Arbitrary display changes are not permitted under the same model. Actual candidate comparisons without expectations failed at `expected_surface` and `expected_final_sram`. Conversely, the intended expectation hash was fixed before candidate native execution from the independent semantics of the original and color conversion, and was not replaced afterward with actual output.

The existing 2-byte test candidate that breaks original app state was also reused as separate evidence. `app_state` fails, while matching the source-derived 5-byte SRAM expectation. The candidate run is not changed to a success merely because the comparison can explain it. A synthetic control with changed model bytes is used only as evidence of rejection before execution, not as a claim about actual firmware behavior.

## New runs and reuse

Completed stock 2.4 material was reused from bw435. For each newly verified stock 2.3 and Faceclaw family, original/candidate display and original/candidate communication ran sequentially, totaling eight native runs. The historical display component had a different hash from the current model, and the historical communication baseline differed from the current profile at preflight. After recording these reasons, one original run of each type was obtained under the same model. Runs were not restarted merely because a stop observation expired.

There were 24 new standalone ARM checks per family, 48 total. The previous 24 stock 2.4 checks were reused. All 67 final matrix audit checks passed. New display and communication captures, saved re-audits, and failures under normal expectations were recorded separately. The public runner, GPU model, and acceptance wording were not changed.

## Evidence and decision boundary

Private `simulator/firmware-comparison-family-matrix-01/` retains family-specific source signature/BL verification, LLVM source and machine code, registration material, pre-execution expectations and provenance, native commands and logs, comparison reports, and auditors. Hash-pinned evidence including reused stock 2.4 material and actual regression/model controls is in `simulator/firmware-comparison-acceptance-manifest.json`. Proprietary main images and private captures are not committed to Git.

E15 completion is limited to **the declared same-condition comparison and classification of intended changes, preservation, and regressions**. Natural GAF calculation, the full UI without a caller, continuous display, all touch/sensors, reset lifetime, and recovery of new environments, missing assets, and stopped processes remain tracked under their respective incomplete conditions. This is not certification of physical installation or recovery compatibility.

The denominator 16 and all acceptance wording remain unchanged. Only E15 changed from partial→done, making the total **9/16=56.25%**. E05/E06/E09/E10/E11/E12/E16 remain. The API display checklist also remains 3/6. There was no physical access, persistent write, subagent, or external posting.
