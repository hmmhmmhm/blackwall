# Registered candidate execution on original UI and render tasks

bw-0433. `run_display_activation_m55.py` selects and runs candidates from the existing raw-main registry. It reuses existing main reset execution, API stimuli, and original UI, display, and renderer tasks. GPU consumption policy, board, input, and observer were not changed here. Unsupported GPU packing and natural GAF initialization boundaries remain.

## Usage

`PY` is private simulator `venv-02/bin/python`, `REGISTRATION` the existing communication-candidate capture. Proprietary images and outputs remain outside Git. The registered original `manifest.json` and corresponding baseline can also be specified directly.

```sh
"$PY" tools/run_display_activation_m55.py "$SIM" "$NEW_CAPTURE" \
  --case stock24 --trace-content --jbd-status-hex 5a01 \
  --gpu-runtime-wake-response 1 --gpu-ring-consumer \
  --gpu-quad-coverage area-reference \
  --firmware-manifest "$REGISTRATION/firmware-candidate.json" \
  --firmware-baseline "$REGISTRATION/firmware-baseline"
```

JBD response, GPU wake, and area-reference are explicit virtual contracts, not physical defaults. Reference coverage does not claim bit identity with actual GPU MSAA. Omitting options retains existing strict policy.

Saved audit validates the capture's registration snapshot and accepts no new candidate:

```sh
"$PY" tools/run_display_activation_m55.py "$SIM" "$SAVED_CAPTURE" \
  --case stock24 --audit-existing --audit-output "$NEW_AUDIT"
```

`--firmware-manifest` and `--firmware-baseline` must be specified together. Mixing saved audit and candidate selection is rejected before preparation/execution. Registration/anchor failures in live selection occur before Docker execution, though a preparation folder may remain.

## Registration and audit contract

New helper `display_firmware_candidate.py` reuses existing registration loader, baseline verification, metadata, anchors, memory-length adjustment, and snapshot functions. It collects 39 addresses including original code addresses in the profile, synthetic caller queue/sender/get entries, and derived stops. Shared helper also includes reset anchor. Registration baseline and display baseline mains must match; candidates changing observer/caller 16-byte code anchors are not run. This is the observation profile's compatibility boundary, not support evidence for arbitrary CFW.

Only selected main and memory length change. Saved audit rechecks candidate hash/declaration, original baseline, display anchors, selected identity, and memory length. Original status and selected-image integrity are distinct. Candidate report says `main_bytes_unmodified=false`, `selected_image_unchanged=true`, not stock bytes. Raw hashes of source-only contract material are compared to original baseline; actual candidate returns, tasks, and buffer results are separately checked from execution observations.

## Execution evidence

An existing 16-byte marker candidate based on stock 2.4 was newly run on pinned Renode M55. It is a registration-path fixture, not an added CFW feature. Candidate 20 checks and semantic contract passed. New candidates for stock 2.3/Faceclaw were not natively run here.

Initially reused `gpu-quad-native-stock24-02` differed in bytes from current `strict.cs`. Even with equal full SRAM, partial surface, and JSON observations, it was not judged a firmware-only comparison. Model difference and first comparison were preserved, and **stock under the same current model was run once to establish a baseline**. First JSON byte difference was key order; observed values themselves matched.

New stock baseline and candidate confirmed:

- Model, board, caller, observer, and GPU component bytes match. Python execution code differs only in candidate memory length.
- Full SRAM at four points and partial L8 surface are byte-identical. Activation/display/content JSON observations also match.
- Original UI, display, and `ambiqdraw` task and stack checks passed. Fourteen GPU lists, 142 draws, and 12 completion/IRQs were observed on the same path.
- 684 nonzero pixels of the 576×288 partial surface match corresponding guest SRAM. Both PNGs were opened and the same nine white dots visually confirmed. This is not a full UI screen.
- Both runs reject at the next register `0x20` command. Frame wrapper not reached; natural main/full frame judgment false.

Private verifier 36 checks and five rejection checks passed. Main mutation, memory-length mismatch, missing anchor list, and registration identity change were rejected; a `0x439c04` code change validly registered in the default registry was also rejected by the display observer contract before execution. Invalid candidates were not run on ARM.

CLI two checks (three selection-argument cases) went red→green; registration 9, existing runtime CLI 9, progress management 14, and Python compile passed. Existing stock 2.4/2.3/Faceclaw display captures were also reaudited from saved data; checks/content/renderer/GPU/status/observed/semantic judgments matched prior results. New ARM execution was one candidate and one current-model stock; the rest were saved checks.

Commands, logs, initial comparison failure, model diff, PNGs, verifier, frozen source, and hash manifest are outside Git in `simulator/display-runtime-candidate-research-01/`.

## Remaining scope

E09/E15/E16 remain partial, scope v3 16 acceptance/status/evidence entries and overall 8/16=50.0%. Natural GAF computation, full display-buffer conversion, display updates over time, and physical verification remain incomplete. Next connect this registered candidate path to saved audit, same-condition comparison, and surface results in the existing CLI, pinning expectations for intended screen differences before execution. Current marker-screen agreement does not establish full UI compatibility of new CFW.

No physical access, persistent writes, CFW user-feature development, subagents, or external publication.
