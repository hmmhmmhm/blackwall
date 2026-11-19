# One-Time Astra Direction Review After IOM6

2026-11-12, bw-0243. At the user's explicit request, one `gpt-6-astra` reviewer was invoked once. The reviewer read project instructions, the existing alignment criteria, current source, and saved evidence. The review involved no new native execution, device access, or external publication. This request does not authorize further automatic Astra invocations.

## Assessment and scope

Continuing original ARM reset execution with strict MMIO is appropriate. Two stock versions and Faceclaw had reached the GPIO117 reset/ready decision after IOM6 retention save and power-off. Because limited state hypotheses influence execution branches, the absence of a forced PC alone does not prove natural boot equivalent to hardware. Full boot, integrated display, and physical recovery remain incomplete.

The product completion criteria remain 13/29 = 44.8%. This ratio is not an estimate of development time or remaining work. Passing the GPIO boundary or increasing the number of tests does not increase it.

## Findings and immediate changes

| Finding | Evidence | Response |
| --- | --- | --- |
| Saved execution provenance and failure of an earlier semantic contract were rejected together | The source `passed` gate in `run_native_candidate.py`. A stock24 exploratory capture failed an earlier frontier expectation but passed a separate saved audit | Added `source_acceptance`. Reusing a failed capture requires valid execution, an explicit audit path and SHA, pinned capture/source files, logs, and reevaluation of the semantic contract. Preserve the raw false and record the acceptance reference in a new derived manifest. |
| A time-based model is not evidence of physical timing | GPIO93 reset and GPIO117 low-to-high are procedures expected by the original firmware. Actual EM9305 startup delay is unknown | Restrict reset/ready follow-up to named hypothesis profiles. Record delays as fixture assumptions and compare nominal, delayed, never-low, and never-ready cases. Do not change signals by read count. |
| Following initialization frontiers risks indefinitely deferring other product areas | S6 in progress, D3 not started, W5 partially complete | End bw242 at the first SPI or unsupported peer response boundary and record unmet scope. Do not keep extending the model with arbitrary peer responses. Next investigate the W5 recovery actor; if blocked, return to the D3 dependency map. |
| Virtual storage receives retransmissions independently of main, so it does not prove survival of the recovery actor | W5 rejects corrupted images before ARM handoff and the host writes stock bytes again | Distinguish virtual byte restoration from successful failure handling by recovery boot. The next W5 investigation must establish the actor receiving, validating, and writing when main is damaged in one connected flow. |

The reviewer read the modified acceptance function and independently matched SHA values for 13 files in the actual stock24 capture. They reported no additional critical code defects. This was a limited review, not verification of the entire repository.

Verification: 13 unit tests passed, along with 15 host checks using actual frozen captures. These included acceptance of a valid audit and rejection of missing or altered hashes, wrong targets, failed execution, and mismatched contracts. The raw report's false and the capture hashes are immutable. Results were preserved in private `simulator/astra-progress-review-20261112-01/report.json`. There was no new native execution.

## Next work selected

1. Continue bw242 to test reset/ready hypothesis causality and failure conditions within a limited scope. Only actual GPIO output and virtual time cause state transitions, preserving existing strict controls. Stop at the first unknown SPI or peer boundary.
2. For W5, first trace one flow in existing recovery boot/transport code to identify who actually receives, validates, and writes when main is unavailable. Do not assume that a recovery transport exists or report host byte restoration as boot failure handling. Physical recoverability remains subject to separate evidence.
3. If W5 is blocked by insufficient evidence, connect D3's `resolved_font` → buffer lifetime → actual renderer caller. Map missing dependencies from the original UI call to framebuffer/submission; do not overstate an independent bitmap test as integrated display or substitute forced UI entry or GPU driver implementation.

Reuse the common runner/plan, pinned models, and saved logs. Do not rerun the same capture for a new semantic contract alone. Run native execution again only for model or execution configuration changes or a specifically documented verification need. The next bw242 model implementation did not begin during this review turn.
