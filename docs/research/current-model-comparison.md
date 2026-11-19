# Current Model Baseline and Candidate Comparison

The bw490 final audit confirmed that the GPU model changed after bw438. An old baseline and a current candidate are rejected before comparison because their model hashes differ. Even after rerunning the baseline on the current model, expecting the old model’s observed trace hash causes failure. Preserve the earlier failure evidence.

Keep the existing pixel and full-SRAM expectations unchanged. Fix the observed trace rule as **matching the current original baseline**. Do not derive expectations from candidate results. Create a new expectation file before starting a new candidate run. If the model changes, reassess this preparation; do not skip hash checks.

## Preparation

After [environment setup](../getting-started/fresh-simulator-workspace.md), `blackwall_python` points to the simulator venv and `blackwall_workspace` to the restored private workspace. Run the commands below from the Blackwall source root. The output directory must be a new path. This scenario is a partial display diagnostic started through an API, separate from a natural full-main UI test.

```sh
"$blackwall_python" tools/run_display_activation_m55.py \
  "$blackwall_workspace" "$blackwall_workspace/current-original" \
  --case cfw --trace-content --jbd-status-hex 5a01 \
  --gpu-runtime-wake-response 1 --gpu-ring-consumer \
  --gpu-quad-coverage area-reference
```

Prepare the trace expectation using only the current original report and existing reviewed expectations. Do not change the expected surface or SRAM hashes.

```sh
"$blackwall_python" - "$blackwall_workspace" <<'PY'
import hashlib, json, sys
from pathlib import Path
s = Path(sys.argv[1])
p = s / 'current-model-expectation.json'
assert not p.exists(), 'Do not overwrite existing expectations'
e = json.loads((s / 'firmware-comparison-family-matrix-01/cfw/predeclared-display-expectation.json').read_text())
r = json.loads((s / 'current-original/verification/report.json').read_text())
assert r['passed'] and 'firmware_candidate' not in json.loads((s / 'current-original/profile.json').read_text())
e['trace_sha256'] = hashlib.sha256(json.dumps(r['observed'], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
p.write_text(json.dumps(e, indent=2) + '\n')
PY
```

## Run and compare a candidate in one command

```sh
"$blackwall_python" tools/run_display_activation_m55.py \
  "$blackwall_workspace" "$blackwall_workspace/current-candidate" \
  --case cfw --trace-content --jbd-status-hex 5a01 \
  --gpu-runtime-wake-response 1 --gpu-ring-consumer \
  --gpu-quad-coverage area-reference \
  --firmware-manifest "$blackwall_workspace/firmware-comparison-family-matrix-01/cfw/registration/manifest.json" \
  --firmware-baseline "$blackwall_workspace/imu-powersave-main-01/cfw" \
  --compare-baseline "$blackwall_workspace/current-original" \
  --comparison-output "$blackwall_workspace/current-comparison" \
  --comparison-expectation "$blackwall_workspace/current-model-expectation.json"
```

`current-comparison/comparison.json` separates intended pixel/SRAM changes from the trace and initial state to preserve. The two PNGs are surfaces from guest SRAM. `current-candidate/verification/report.json`, `renode.log`, and the process journal record execution and semantic judgments and the reason for termination.

This API diagnostic is a partial scenario that rejects unsupported textures at `Texture state requires explicit reference profile`. Do not interpret `passed` as proof that the full UI or GPU is defect-free. Natural display/app execution is verified with separate functional models in [E05](../firmware/native-main-boot-acceptance.md), [E09](../hardware/display-gpu/first-native-dashboard-frame.md), and [E10](../bootloader/post-screen-boot-lifecycle.md). This does not include physical-device access, installation, or firmware product development.
