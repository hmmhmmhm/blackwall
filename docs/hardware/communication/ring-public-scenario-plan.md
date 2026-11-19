# Public Ring wake scenario implementation plan

bw-0458. This details implementation of the approved v3 E11/E16 input scenario integration. Codex works alone in the current working copy. It includes no new product feature, CFW code, physical device, external publication, or Git commit. Existing user instructions and preservation of the current working copy take precedence over general skill defaults recommending automatic subagents, separate approval, or commits.

## Design

Moving the entire private research script to the CLI would implicitly read historical research folders and source addresses. Adding a ring branch to the existing runtime CLI body would mix connection/ATT reporting contracts. Therefore choose a standalone scenario module and small CLI entry point reusing existing `run_runtime_connection_m55.build`. Existing implementation supplies Docker lifecycle, prerequisites, and registered-candidate verification.

V1 has one `ring-wake` scenario. Put fixed ABI profiles for the three originals in public JSON, checking baseline raw SHA and observation-address anchors. A registered candidate must pass existing registration and is rejected before execution if the ring observation ABI changes. Reports distinguish UI callback entry from unverified callback return, pixels, and normal GAF. Do not create a generic plugin, user script execution, automatic firmware download, or BLE access.

## Files and roles

- `tools/ring-input-profiles.json`: fixed baseline SHA, ring/app/wake/UI addresses, and observer anchor SHA from bw455–457. Contains no proprietary main bytes.
- `tools/renode-ring-wake-observer.cs`: preserves the existing authored private WakeRequest/RX observer as public source.
- `tools/ring_wake_runtime.py`: verified IronPython scenario body. Bounded stages are original report→actual 108/ACK→original app/app 1 request/response→UI entry.
- `tools/ring_input_scenario.py`: `build(simulator,output,case,firmware_manifest=None,firmware_baseline=None)` and `inspect(output,destination)`; combines runtime builder/current UART/existing shared IOM profile and observer, and performs independent semantic checks. Does not read historical research paths.
- `tools/run_ring_input_m55.py`: help, case/registered-candidate arguments, saved audit, prerequisites, execution, and exit status. Help does not import the ARM package.
- `tests/test_ring_input_cli.py`: checks actual subprocess help, invalid candidate arguments, invalid audit output, missing-asset rejection, and absence of output side effects.
- `docs/hardware/communication/ring-public-scenario.md`: preparation, one-run command, registered candidate, saved audit, artifacts, and limitations.

## Sequence

- [x] First test CLI help/argument rejection and preserve the red result from the absent tool. This boundary must run without native/asset access.
- [x] Separate pinned profile and observer/runtime from previously verified actual inputs. Check that public profile SHA/addresses match pinned raw and the new runtime does not read private folders.
- [x] Implement build, inspect, and CLI. Allow only new output paths under the simulator root outside Git and require both candidate arguments together. Use existing build `firmware_manifest`/`firmware_baseline` API. Update existing capture input hash list for new model/board/runtime/profile/snapshot, then pin with `pin_capture`.
- [x] Confirm cheap CLI checks green. `--audit-existing` requires a separate new audit path that does not modify the original capture and does not execute it. Help/argument errors exit before Docker/ARM package checks.
- [x] Run stock 2.4 ring wake with the public command and compare against bw457 fixed input, five-stage SRAM, and original observation prefix. Run an actual registered candidate too, checking selection of a SHA different from original main and handling of the same ABI/scenario.
- [x] Run saved audit in a separate folder and confirm the same decision as live analysis. Check rejection of changed source profile/execution/model/board hashes and missing assets. Record native failures distinguishing execution and semantic results.
- [x] Update documentation, manifest, and work record. Retain E11/UI/frame/GAF incomplete and overall 10/16=62.5%.

If a new workspace of the existing 498 files already contains the required prefix, run from that root to prevent implicit dependence on the original asset root. If legitimate assets are missing, explicitly add only the necessary read closure without silently changing the existing lock. When rerunning the same native input, record the differences of public path, candidate, and independent workspace verification.

Result: [public execution procedure](ring-public-scenario.md). Three originals/registered candidate, actual ARM regression candidate, saved audit, and missing assets were checked. Model code changes 0; UI/frame/GAF remain incomplete; overall 62.5% retained.
