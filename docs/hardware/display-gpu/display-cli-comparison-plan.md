# Display execution and comparison CLI integration plan

bw-0434. Within existing approved E15/E16 tool scope, connect the same comparison selection as runtime CLI to display runner. No separate runner; reuse original display audit. Full UI and natural-main limits remain.

- [x] First create failure tests for CLI selection errors/pre-execution rejection and full byte/hash comparison.
- [x] Reuse candidate semantic-change rules and compare synthetic caller entries with actual assembly.
- [x] Compare profiles and run inputs; reject model/board/observation/input or code differences other than allowed memory length before execution.
- [x] Audit both records and confirm guest SRAM/L8 surface match. Compare full hashes of surface, final full SRAM, and canonical trace; display only first 64 pixel differences. A truncated difference list alone cannot pass.
- [x] Default expectation is stock baseline. Optional expectation file specifies schema1, candidate pass, failed-check list, and surface/final SRAM/trace SHA256. Preserve expectation provenance and pre-execution pinning separately.
- [x] Verify saved CLI, old-model rejection, synthetic differences/candidate failure judgments, and one new M55 marker plus shared comparison. Do not rerun existing stock under same model.
- [x] Record execution commands, verification, logs, frozen source, manifest, and incomplete boundaries.

Final exit 0 requires both candidate verification and comparison pass. Actual executed CFW with intended screen change is not replaced by marker/synthetic-byte tests. Acceptance and overall 50% do not change from this unit. Execute sequentially in current shared work; no subagents, Git publication, or physical access.

Result: [execution, synthetic controls, and incomplete boundaries](display-cli-comparison.md). Intended screen change by actual ARM is the next functional verification unit; marker/synthetic results do not substitute for it.
