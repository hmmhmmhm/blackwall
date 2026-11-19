# Runtime Execution and Comparison with Stock Baseline

bw-0432. The existing runtime CLI can compare a registered-candidate run or saved audit against a stock capture of the same scenario. It reuses the existing comparison API instead of creating a separate runner. Firmware, device models, and scenarios were unchanged.

## Usage

The variables below refer to existing registration material inside the private simulator and new output paths. `PY` is `venv-02/bin/python`. Do not commit original images or captures to Git.

```sh
"$PY" tools/run_runtime_connection_m55.py "$SIM" "$NEW_CAPTURE" \
  --case stock24 --att-time \
  --firmware-manifest "$REGISTRATION/firmware-candidate.json" \
  --firmware-baseline "$REGISTRATION/firmware-baseline" \
  --compare-baseline "$STOCK_CAPTURE" \
  --comparison-output "$NEW_COMPARISON"
```

To re-audit saved records only, use the following; it performs no new ARM execution.

```sh
"$PY" tools/run_runtime_connection_m55.py "$SIM" "$SAVED_CANDIDATE" \
  --case stock24 --audit-existing --audit-output "$NEW_AUDIT" \
  --compare-baseline "$STOCK_CAPTURE" \
  --comparison-output "$NEW_COMPARISON"
```

Add `--comparison-expectation "$EXPECTED_JSON"` only when comparing a predeclared regression. Results are saved in `comparison.json`. Candidate execution judgment `candidate_passed` and comparison judgment `comparison_passed` are printed separately; only when both are true is final `passed=true` and exit 0. Even when an expected regression matches, candidate verification failure remains exit 1. Omitting comparison options preserves existing output format and assessment.

## Preflight

Existing comparison API input checks were separated into `preflight()`. Before execution it checks profile, model/board/observer/input hashes, and that execution code is identical except for firmware candidate memory length. Comparison output must be a new path inside the simulator and cannot be inside either capture. For live execution, checks run after preparation files are created but before Docker execution. Therefore a rejected run may leave a preparation folder, but ARM does not execute. For saved audits, rejection occurs before audit-folder creation.

## Verification results

| Path | Candidate judgment | Comparison judgment | Exit code |
| --- | --- | --- | --- |
| Saved marker candidate | Pass | Pass | 0 |
| Saved regression candidate with predeclared expectation | Fail | Pass | 1 |
| Saved regression candidate with normal expectation | Fail | Fail | 1 |
| New Renode marker run | 28 checks passed | Pass | 0 |

The new run executed the registered ARM binary on M55 in the pinned Renode image. The existing stock baseline was not rerun. Comparison JSON from the new run and saved marker matched byte-for-byte, as did the existing frozen marker comparison and existing regression comparison respectively. Summary and verification from saved audit without the option also matched existing output.

Six CLI selection/preflight-rejection checks, three optional-import checks, and 14 progress-management checks passed. Initially, testing did not start because system Python lacked `unicorn`; rerunning in the existing venv passed. The first marker comparison reference predated addition of the `sram_changes_truncated` field, so byte comparison failed. After confirming the difference was the single absent/false field, comparison used the existing frozen-marker record with the same schema. The first result and correction reason were retained.

Material, commands, failure/success records, and frozen source are retained in private `runtime-cli-comparison-research-01/manifest.json`. Supported scope is the pinned device communication → original app task → RTC scenario. This candidate is a 16-byte marker fixture and does not establish full Faceclaw compatibility. Natural GAF initialization, full boot/UI, automatic frame comparison, and complete new-environment setup remain incomplete. E15/E16 remain partial; overall is 8/16 = 50.0%.

The next unit is to define how to connect an already verified display scenario to the shared execution/result format and record display evidence separately from communication captures. Normal GAF computation can resume only after actual code/ROM contracts or independent input/output expectations are obtained. No physical access, firmware writes, external publication, or subagent invocation occurred.
