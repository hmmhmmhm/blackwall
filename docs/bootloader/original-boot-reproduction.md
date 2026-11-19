# Reproducing original boot → main → screen

> This is a low-level reproduction record from the earlier research environment. For current user-facing commands, use the [Docker volume guide](../getting-started/emulator-report-quickstart.md).

This is a verified virtual single-temple profile for stock 2.4.0.24. It starts at the original bootloader reset vector; it does not include actual Boot ROM reset or physical-device validation. It provides no installation, OTA, or physical BLE discovery feature.

## Required pinned assets

`docs/data/original-boot-stock24-profile.json` pins the original boot/main SHA, length, SP/reset vector and addresses; initial SRAM/ITCM fills; model, board, observation, and runtime source hashes; and Docker image ID. In the historical environment the proprietary firmware and verified frozen model had to be outside Git at `~/Library/Application Support/Blackwall/`. It does not automatically download other versions or infer offsets.

The model depends on the frozen sources in `simulator/original-boot-ui-cadence-native-bw547-02`. The general Blackwall runtime and screen observer sources are `tools/renode-original-boot-runtime.py` and `tools/renode-complete-screen-observer.cs`. The saved sources are verified without retroactively making an old profile depend on the current candidate builder. This does not mean a clean clone can recreate proprietary assets. Execution stops before the run if an asset is missing or a hash differs.

## Run with one command

From the repository root, specify a new private output path:

```sh
blackwall_private="$HOME/Library/Application Support/Blackwall"
blackwall_python="$blackwall_private/simulator/venv-02/bin/python"
"$blackwall_python" -B tools/run_original_boot_screen.py \
  --private-root "$blackwall_private" \
  --output "$blackwall_private/simulator/original-boot-screen-repro-01"
```

Existing output is not overwritten. `--derive-only` stops after validation and preparation of the manifest and executable files. The default run sequentially executes pinned Renode Docker without networking, audits before cleanup, removes reproducible duplicate dumps, and audits again afterward.

`execution_passed` means the Renode process exited successfully. `semantic_validation.passed` and the final `passed` separately check original boot/main order, stack-bank lineage, virtual wire ID/CRC correlation, UI/rendering, same-time guest RAM/frame equality, and all captured guards. The CLI exits with status 1 if display validation fails, even when the process exited normally.

The initial observation is limited to 20 virtual seconds or 300 host seconds, with a 420-second container limit. It then applies a 1 ms virtual GPIO27 pulse, handles original UART requests and responses, and applies the existing functional cadence change from 10 to 167 MIPS at HP mode 22 during actual UI dispatch. It does not directly write the original PC, branches, TCB, queue/readiness, or memory. CPU, time, and all SRAM are compared before and after the cadence change. Read-only observation stops at post-store PC `0x560f6a` in the original GPU register writer at the first nonuniform completed frame.

## Independent audit without rerunning

```sh
"$blackwall_python" -B tools/run_original_boot_screen.py \
  --audit-existing "$blackwall_private/simulator/original-boot-screen-repro-01" \
  --audit-output "$blackwall_private/simulator/original-boot-screen-repro-01-independent-audit"
```

The audit writes a report to a new directory without modifying the original execution directory. It rechecks source/asset/retained-artifact SHA, consistency between the original native log and exported JSON, raw frame/guest RAM byte equality, and protection violations. For removed image dumps and pre/post-cadence copies, it uses per-original SHA/equality evidence calculated before cleanup; it does not claim to reread missing raw files.

Input timing and fade values can vary slightly because of initial host polling. Repeated runs independently validate boot/main/UI/frame conditions with the same profile, sources, and initial assets. No claim is made that the complete CPU/time/raw-frame SHA is always identical. Each frame must match the actual guest RAM from the same time.

## Failure input

```sh
"$blackwall_python" -B tools/run_original_boot_screen.py \
  --scenario unknown-boot-marker \
  --private-root "$blackwall_private" \
  --output "$blackwall_private/simulator/original-boot-unknown-marker-repro-01"
```

This mode changes only the virtual OTA marker profile to `unknown`. A strict guard stops execution at actual PC `0x42e582`, where the original boot reads `0x7fe000`; there must be no handoff, main, screen, or external input. Exit status 0 means **the expected rejection was verified**, not that boot succeeded. An unknown state is not classified as safe by the normal profile.

Files supplied through `--boot-image`/`--main-image` must match the same pinned original SHA, length, and vectors. Rejecting corrupt or different-version inputs is host preflight validation; it does not establish successful cryptographic image validation by the bootloader.

## Retention and cleanup

Retain the manifest, original source and hashes, launcher, native log, raw frames/previews, final guest SRAM, audit reports, and cleanup records. Remove verified duplicate guest boot/main and pre/post-cadence SRAM copies promptly. Preserve canonical originals and modified dumps needed for diagnosis. Identify owned Docker resources by journal before removing them; do not terminate another task's processes.

`contrast-preview.png` scales up dark raw values from the initial fade for readability. Distinguish it from raw A8 values and physical brightness. Functional device, public GAF defaults, constant ADC, reference GPU, and cadence assumptions remain in effect; they do not guarantee actual sensor fusion, the entire GPU ISA, RF behavior, or physical power characteristics.
