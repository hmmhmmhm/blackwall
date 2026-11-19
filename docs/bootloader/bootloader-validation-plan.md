# Bootloader Validation Plan

2026-11-17 · bw-0553. The user approved validation items 1–4 in `bootloader-validation-gaps.md`. Work proceeds sequentially while preserving uncommitted material in the existing work directory. Physical devices, external publication, subagents, and new CFW functionality are out of scope.

## Design and verdicts

Reuse the frozen model from the existing original boot profile and provide a separate boot scenario runner. Do not weaken the original runner's SHA gate. The new runner permits only pinned originals, the pinned research patch, and explicit corruption fixtures. Native observations do not modify CPU, memory, or branches. If ROM is unavailable, report the first boundary without mocking a successful return.

Distinguish isolated ARM tests, functional models, and natural full execution. Record `reviewed` and `verified` separately. The 12 conditions below form the full denominator; count only passed conditions toward completion. Partial verification and unsupported behavior are not complete. These 12 conditions do not establish physical safety certification.

| ID | Stage | Completion criterion |
| --- | --- | --- |
| BV01 | 1 | Pinned assets/scenarios, non-intervention in original runtime, automated result classification and negative tests |
| BV02 | 1 | Actual original boot selection paths and termination/rejection for clear/pending/corrupt markers |
| BV03 | 1 | Actual boot handling of invalid main SP/reset/ranges, distinguishing fault from unsupported behavior |
| BV04 | 2 | Natural path from research-patched boot reset through worker/main |
| BV05 | 2 | Actual same-board UART2 authentication, invalid authentication, timeout/retry handling |
| BV06 | 2 | Same-board recovery command completion→natural main entry and original control |
| BV07 | 3 | Explicit virtual MRAM request/alignment/permission and success/failure contract, with original calls verified |
| BV08 | 3 | Changed bytes at update interruption points and boot selection after new reset |
| BV09 | 3 | Boot/metadata/neighbor protection and invalid-write rejection on failure/interruption |
| BV10 | 4 | Virtual stock application restoration, full main hash, and natural reboot |
| BV11 | 4 | Virtual full-stock restoration, hashes of all changed persistent components, and reboot |
| BV12 | 4 | Version-specific boot/main/recovery combination table, repetition, and unsupported combination rejection |

## Execution units

- [x] Compare assets/source/reports from the existing upstream 118 tests, writer four conditions, and two original cold cases to avoid duplicate runs.
- [x] First add tests to `tests/test_boot_validation.py` for invalid inputs, prevention of false unsupported/timeout verdicts, and non-intervention in source; record failures.
- [x] In `tools/run_boot_validation.py`, validate and copy the existing profile and create separate read-only private fixtures. Execute marker clear/pending/corrupt, main SP/reset, and patched boot sequentially, recording original trace/guard/fault/image SHA.
- [x] Poll the existing `execute` ownership journal for each native run and immediately clean duplicate firmware dumps and temporary inputs afterward. Preserve source/hashes/logs/key final states.
- [x] Compare original source/instructions at actual boundaries with existing model contracts. Proceed to the next unit when inputs alone can resolve the issue; report ROM/unsupported UART/write boundaries separately.
- [x] Check whether existing resident writer and recovery source support MRAM partial/interruption and restoration, and add feasible tests. Do not declare recovery complete solely from a host byte copy whose outcome is determined by model assumptions.
- [x] Update evidence and remaining boundaries for all 12 conditions in `bootloader-validation-progress.json` and the results document. Do not display 100% without full completion.

When a condition is blocked, record the evidence and specific inputs/models needed to resume, and continue independently testable conditions. Do not bypass boundaries with arbitrary PC/success returns, disabled protection, or physical access.
