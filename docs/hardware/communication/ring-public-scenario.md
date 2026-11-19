# Public Ring wake execution tool

bw-0458. `tools/run_ring_input_m55.py` executes original main reset → virtual ring relay → original ring task → actual 0x108 request/peer ACK → app state change → app 1 request/response → UI callback entry. The CLI does not directly set helper, callback, PC, TCB, or readiness. It uses existing UART RX/timeout and explicit shared-IOM profile from the [verified original path](ring-app-wake-contract.md).

It stops on UI callback entry, so callback completion, guest frame, continuous display, and normal GAF computation remain unverified. This models a virtual opposite-temple UART relay contract, not direct R1 BLE. All 16 v3 conditions and 10/16=62.5% remain.

## Preparation and original execution

For Python, wheel, Docker, and pinned Renode image, follow the [existing fresh-environment procedure](../../getting-started/fresh-simulator-workspace.md). A new Ring workspace needs 62 files/63,471,313 bytes in `tools/simulator-ring-workspace-lock.json`, a list tracing actual host read closure for runtime build and registered-candidate preparation. Proprietary firmware images are neither supplied nor committed to Git. Restore from lawfully retained existing assets; the existing 498-file lock was unchanged. The existing workspace alone lacks three verified assets for explicit GAF configuration, so use this dedicated lock.

From the Blackwall repository root, choose actual paths and run to a new output:

```sh
blackwall_assets="$HOME/Library/Application Support/Blackwall/simulator"
blackwall_ring="$HOME/Library/Application Support/Blackwall/my-ring-workspace"
blackwall_python="$HOME/Library/Application Support/Blackwall/development-bootstrap-bw438-01/venv/bin/python"
python3 tools/restore_simulator_workspace.py tools/simulator-ring-workspace-lock.json "$blackwall_assets" "$blackwall_ring"
"$blackwall_python" tools/run_ring_input_m55.py "$blackwall_ring" "$blackwall_ring/stock24-run" --case stock24
```

`--case` supports `stock24`, `stock23`, `cfw`. Pinned baseline SHA and 16-byte SHA at each ring/app/UI observation point are checked. A generic new ABI is not guessed and accepted. Output must be a new path below the private simulator root outside Git. Existing captures are not overwritten. Docker runs the pinned image with network none; there is no automatic image pull, physical access, or firmware installation feature.

## Registered candidate

Specify the existing raw-main registration manifest and its baseline together. This dedicated workspace also contains the previously verified Faceclaw-family RGB-zero test candidate.

```sh
"$blackwall_python" tools/run_ring_input_m55.py "$blackwall_ring" "$blackwall_ring/cfw-candidate-run" --case cfw \
  --firmware-manifest "$blackwall_ring/firmware-comparison-family-matrix-01/cfw/registration/manifest.json" \
  --firmware-baseline "$blackwall_ring/imu-powersave-main-01/cfw"
```

Ring-observer ABI checks supplement existing registration and vector/extent/runtime anchor validation. Unsupported observation ABI is rejected before VM execution. The actual drawing effect of RGB-zero code occurs after this ring scenario's stop, so this run does not verify that color behavior. A separate role regression candidate also verifies when changed ARM instructions alter actual input content.

## Outputs and saved audit

- `verification/report.json`: `execution_passed` and semantic `passed`, original task/return, ACK/ID, role/code, UI entry judgments, actual events, and unverified capabilities.
- `exports/ring.json`, stage-specific `*-sram.bin`: original execution observations and actual SRAM. No prebuilt host screen.
- `ring-profile.json`, `ring-source-profile.json`, `connection-inputs.json`, `capture-files.json`: reproducibility material for pinned scenario/version/source ABI/model/board/input/output.
- `renode.process.json`: existing owned-process lifetime journal, using the same owner checks as [process recovery](../../architecture/native-process-recovery.md).

With valid output/assets, success exits 0; semantic failure retains a report and exits 1; invalid arguments, missing assets, or capture hash mismatch exit 2. If initial harness error prevents export, runtime error and missing export are reported as failures. Help reads neither ARM package nor private firmware.

Audit saved captures in a separate new audit folder. This command does not run Docker.

```sh
"$blackwall_python" tools/run_ring_input_m55.py "$blackwall_ring" "$blackwall_ring/stock24-run" --case stock24 \
  --audit-existing --audit-output "$blackwall_ring/stock24-audit"
```

The audit uses the saved registration snapshot without specifying the candidate again. Audit output cannot be placed inside or above the original capture; model/board/input/output hash and console/export mismatches are rejected. A current raw SHA that is not original is not treated as original without a registration snapshot.

## Verification scope

A separate empty workspace was restored from 62 files, blocking host reads and Docker binds from the existing simulator root during execution. Actual CLI runs of three originals and a registered candidate, comparison of stock 2.4 with bw457 stage SRAM, separate saved audits, and model-change rejection were confirmed. Three originals plus the registered candidate exited 0. A separate regression candidate changes the original two-byte `MOVS r0,#4` instruction to `#5`, a one-byte difference; under the same model/board/observation configuration actual ARM sent source 5. It reached UI callback, but `actual108_wire`, `source_role_code`, and `app_state` failed and it exited 1. Normal VM execution was distinguished from semantic regression.

There were five new native runs. All five captures were separately audited under a Docker-call prohibition guard, confirming identical judgments and unchanged original captures. Stock 2.4/2.3 live reports produced before console/export consistency checks were added were preserved and re-audited with the new checks; common checks and semantic values matched. All six SRAM checkpoints from stock 2.4's prior bw457 were exact. A model-changed capture was rejected with exit 2 before creating audit output. Ten CLI/ABI boundary checks and 45 final aggregation checks passed.

Four execution read-closure collections reached preparation only and are not counted as firmware runs. Missing GAF assets and partial output in the first existing-workspace attempt, and an incorrect import name during regression-fixture preparation, were retained diagnostically. All five runs' owned processes were removed. Evidence is pinned in private `simulator/ring-public-scenario-research-01/acceptance-report.json` and `ring-public-scenario-manifest.json`. UI entry success in this document must not be read as display output or overall goal completion.
