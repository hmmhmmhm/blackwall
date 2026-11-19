# Fresh simulator workspace

> This document records an earlier research environment. For current installation and execution, use the [Docker volume guide](emulator-report-quickstart.md).

When reproducing with current code, also follow the [bw490 model refresh and comparison procedure](../research/current-model-comparison.md). The bw438 commands below use the pinned model baseline from that time. Mixing the latest GPU model with the older baseline causes the protection check to reject the run; do not disable it.

Using the existing Mac's Docker and LLVM installations, bw438 reproduced the pinned scenarios in a **new Python virtual environment and empty private asset root**. This was not a fresh OS installation or validation on another Mac. Keep firmware outside Git.

## Supported environment and preparation

- macOS arm64, Python 3.14 (execution validated with 3.14.4), and Docker.
- LLVM/LLD 21: `/opt/homebrew/opt/llvm@21/bin/{clang,llvm-objcopy}`, `/opt/homebrew/opt/lld@21/bin/ld.lld`.
- Renode 1.17 and .NET 8.0.16 Linux arm64 image `sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649`. See the [Renode environment](../architecture/renode-m55-probe.md) for restoration/build evidence. Other images are not automatically substituted or pulled.
- Prepare the Unicorn 2.1.4 and Capstone 5.0.9 wheels from `tools/simulator-wheels.json` locally. Installation is offline and rejects hash mismatches.
- The private assets pinned in `tools/simulator-workspace-lock.json` are required: 498 files totaling 449,890,129 bytes. This is the execution read closure for three original images, test candidates, baseline captures, models, and predeclared expectations. It does not imply support for arbitrary new ABIs.

From the Blackwall repository root, set these variables to the actual paths. The virtual environment and workspace outputs must be new paths outside Git. `blackwall_assets` is the existing private simulator asset root.

```sh
blackwall_assets="$HOME/Library/Application Support/Blackwall/simulator"
blackwall_fresh="$HOME/Library/Application Support/Blackwall/my-fresh-workspace"
python3 tools/setup_simulator.py --wheels "$blackwall_assets/wheels/macos-arm64-py314-01" --output "$blackwall_fresh/venv"
python3 tools/restore_simulator_workspace.py tools/simulator-workspace-lock.json "$blackwall_assets" "$blackwall_fresh/workspace"
blackwall_python="$blackwall_fresh/venv/bin/python"
blackwall_workspace="$blackwall_fresh/workspace"
```

The restorer first checks the size and hash of every input, then rechecks the hashes after copying. It rejects existing output, paths inside Git, path traversal, and completion-marker collisions. A copy failure can leave a partial directory without a completion marker; preserve it for diagnosis and use another new output path.

## Run and compare a candidate with one command

The **single execution command** below runs a registered Faceclaw-family RGB-zero ARM test candidate on actual Renode M55 and stores the display surface, events, stop reason, and comparison with the baseline. Initial installation and asset restoration are the preparation steps above. It does not overwrite an existing output path.

```sh
"$blackwall_python" \
  tools/run_display_activation_m55.py \
  "$blackwall_workspace" \
  "$blackwall_workspace/documented-cfw-run" \
  --case \
  cfw \
  --trace-content \
  --jbd-status-hex \
  5a01 \
  --gpu-runtime-wake-response \
  1 \
  --gpu-ring-consumer \
  --gpu-quad-coverage \
  area-reference \
  --firmware-manifest \
  "$blackwall_workspace/firmware-comparison-family-matrix-01/cfw/registration/manifest.json" \
  --firmware-baseline \
  "$blackwall_workspace/imu-powersave-main-01/cfw" \
  --compare-baseline \
  "$blackwall_workspace/firmware-comparison-family-matrix-01/cfw/display-original" \
  --comparison-output \
  "$blackwall_workspace/documented-cfw-comparison" \
  --comparison-expectation \
  "$blackwall_workspace/firmware-comparison-family-matrix-01/cfw/predeclared-display-expectation.json"
```

The validation run used the same arguments under the `development-bootstrap-bw438-01` root. The original command and exit status 0 are retained in `documented-direct-command.json` and `documented-direct-result.json`. The direct execution without an audit wrapper also matched the Faceclaw display comparison in the six isolated runs.

Outputs:

- `documented-cfw-run/verification/report.json`: 20 checks covering the original RTOS task/stack, API diagnostic boundary, and execution/semantic results.
- `documented-cfw-run/exports/gpu-last-frame.bin`: a 576×288 L8 partial surface read from guest SRAM.
- `documented-cfw-comparison/{baseline-surface.png,candidate-surface.png,comparison.json}`: actual pixels, the intended 684-byte final SRAM change, and event-trace retention result.
- `documented-cfw-run/renode.process.json`: owned-container lifecycle journal. For cleanup after forced termination, follow [interrupted process recovery](../architecture/native-process-recovery.md).

This is a diagnostic using an inserted API caller. `natural_main_complete=false` and `full_ui_verified=false`; it does not establish a full UI frame, normal GAF calculation, or completion of natural main execution. The GPU uses the explicitly declared `area-reference` virtual contract. It does not guarantee physical hardware MSAA accuracy or installation compatibility.

## Missing inputs and failures

Both public CLIs provide `--help` without optional packages. Actual execution and auditing require exact Python packages. Missing packages or version mismatches point to `setup_simulator.py`; missing private assets point to the restorer; and missing project sources point to restoring the same checkout, with exit status 2. Docker, compilers, and the pinned image are also checked before execution. The image is inspected only and not downloaded automatically. General program defects are not disguised as missing assets.

Guidance for a missing package, missing private assets, and a nonexistent image was tested in actual processes. Missing Docker/compilers and version mismatches were tested using unit mocks. No service was stopped and no system tool was deleted.

## Validation scope

Verified Python modules and both native library paths inside the new virtual environment. Across six stock 2.4/2.3 and Faceclaw-family candidate display/phone runs, host file reads and Docker binds from the old asset root were blocked. All exited with status 0, with zero reads from the previous root; the display had 20 checks, the phone had 28, and each comparison passed. One direct execution also passed, for seven successful new native runs. The first attempt failed before VM startup because a nested output parent was missing; the record was preserved and parent creation was fixed. A completion-marker `./` path-alias collision was also blocked by a regression test.

The higher-level completion decision follows the [E16 development-tools acceptance audit](../project/development-tools-acceptance.md); regression limits for original/candidate scenarios are in the [E15 comparison audit](../firmware/firmware-comparison-acceptance.md).
