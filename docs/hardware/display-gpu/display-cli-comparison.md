# Display execution, saved audit, and baseline comparison

bw-0434. One command in the existing display CLI runs a registered candidate or saved audit and compares it with stock under the same model. `compare_display_firmware.py` reuses the existing display auditor. Comparison PNGs are generated from L8 surfaces matching actual guest SRAM and are not presented as full UI output.

## One-command use

`PY` is the private simulator's `venv-02/bin/python`. Actual audit requires this environment's ARM analysis dependencies. All capture and comparison outputs use new paths inside the private simulator.

```sh
"$PY" tools/run_display_activation_m55.py "$SIM" "$NEW_CAPTURE" \
  --case stock24 --trace-content --jbd-status-hex 5a01 \
  --gpu-runtime-wake-response 1 --gpu-ring-consumer \
  --gpu-quad-coverage area-reference \
  --firmware-manifest "$REGISTRATION/firmware-candidate.json" \
  --firmware-baseline "$REGISTRATION/firmware-baseline" \
  --compare-baseline "$ORIGINAL_CAPTURE" \
  --comparison-output "$NEW_COMPARISON"
```

To use a saved capture, inspect without new ARM execution:

```sh
"$PY" tools/run_display_activation_m55.py "$SIM" "$SAVED_CANDIDATE" \
  --case stock24 --audit-existing --audit-output "$NEW_AUDIT" \
  --compare-baseline "$ORIGINAL_CAPTURE" \
  --comparison-output "$NEW_COMPARISON"
```

Comparison output includes `comparison.json`, new audit reports for both captures, `baseline-surface.png`, and `candidate-surface.png`. For comparison alone use `compare_display_firmware.py SIM BASELINE CANDIDATE OUTPUT`. Existing CLI output/judgment remains when comparison options are omitted.

## Pre-execution equivalence checks

Profiles are compared allowing only candidate registration metadata and its selected-image semantic rules. Three function entries of the synthetic caller are recovered from actual captured assembly and compared to the profile. Registration helper and comparator use the same function for candidate semantic-contract change rules.

Board, initial memory, execution script, C# model, observer, caller, and JBD source proof must match. Only verified main-memory length differences are allowed in execution Python. Historical records with different models or different coverage, input, or observation profiles are not treated as firmware-only comparisons. Live path rejects before Docker start after preparation; saved path rejects before audit-folder creation.

## Judgment rules

Default expectation is stock results under the same model. Full SRAM at initial, UI transition, and display transition must match; final full SRAM, surface, and canonical event-record full SHA256 are compared. Canonical records sort JSON keys only and preserve event arrays and values. Surface width, height, stride, address, and agreement with actual guest memory are checked.

For intended differences, specify a file pinned before execution with `--comparison-expectation`. Exact schema 1 fields are `candidate_passed`, `failed_checks`, `surface_sha256`, `final_sram_sha256`, `trace_sha256`, and `schema`. SHA256 is 64 lowercase characters and candidate judgment boolean. Verification code does not authenticate independent provenance of expectations. Expectations copied retrospectively from results are not claimed as verification of intended change.

Only the first 64 differing bytes are displayed with coordinates, but total difference count and hash are checked. Passing is not based solely on a truncated list. Comparison success and candidate verification success are separate judgments. Shared execution CLI exits 0 only when both pass; even expected audit failure retains final exit 1. Separate comparison CLI reports comparison judgment only.

## Actual execution and controls

Before execution, marker-preservation expectations were pinned from bw433 stock material under the same model. **One new M55 marker run passed 20 candidate checks and shared comparison, with zero surface differences.** Stock baseline was not rerun. Shared comparison of saved marker passed; new execution, saved record, and final comparator results agreed. PNG CRC and every decompressed pixel matched guest surface.

Six controls mutating saved records produced expected results. These are **synthetic artifact tests** of the comparison tool, not evidence of actual CFW/CPU behavior changes.

| Control | Confirmed result |
| --- | --- |
| Change 71 bytes of surface and corresponding SRAM, normal expectation | Candidate audit passes; comparison fails, exit 1 |
| Same synthetic change, precomputed full hash | Comparison passes, exit 0; only 64 of 71 differences displayed |
| Change activation fault field, expect audit failure | Candidate fails; comparison passes; final exit 1 |
| Change surface alone, retain guest SRAM | Detached surface rejected |
| Change model bytes in same profile | Rejected before audit |
| Incomplete expectation file | Rejected before audit |

Historical-model captures were also rejected for profile differences before audit. Public screen 9, existing runtime CLI 9, registration 9, and progress-management 14 checks passed. After adding final SRAM length check, the same saved results were used to reverify final comparison and PNG without another native run. First final audit command mistakenly used system Python and failed on missing `unicorn`; its empty output folder was preserved and the designated venv/new path passed.

Commands, expectation provenance, logs, synthetic-control labeling, frozen source, and hash manifest are preserved in private `simulator/display-cli-comparison-research-01/`. No physical access, firmware installation, subagents, or external publication.

## Next feature verification

This native candidate is a preservation marker. **A candidate whose actual ARM code creates an intended screen change and an independent pixel expectation have not yet been verified.** Next analyze a test variation limited to a supported original draw path, pin change/preservation conditions before execution, and compare an actual candidate run. Synthetic byte controls do not complete this item.

GPU final display-buffer conversion still stops at register `0x20`. Natural GAF initialization, full main/UI, continuous display, and complete new-environment installation/missing-assets/interrupted-process cleanup remain incomplete. E09/E15/E16 partial; scope v3's 16 conditions and overall 8/16=50.0% remain.
