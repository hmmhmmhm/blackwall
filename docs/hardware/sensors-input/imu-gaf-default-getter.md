# Source-pinned GAF getter and original main integration

bw350. **Natural main in stock 2.4, stock 2.3, and Faceclaw38 completed the 41-field, 153-byte GAF read and advanced to the next magnetometer-bias write.** Original ARM instructions, branches, returns, TCB, and stack were unchanged; no API test caller or callee stub was inserted. No physical glasses were accessed.

This run explicitly selects the [TDK public defaults research profile](../../data/imu-gaf-default-profile.json) as a virtual IMU condition. Its values are not established as physical G2 ROM defaults. The public/embedded calmag patch difference and unverified sensor fusion remain in the [consumer contract](imu-gaf-configuration-contract.md).

## Supported model scope

The same explicit ROM-result fixture structure as the existing power-save input is used. Without `gafParametersHex`, no new object is created and the existing strict boundary remains. The new field map contains 41 fields whose addresses, widths, and structure offsets were checked against source and all three originals.

- After confirming power-save completion, two existing service completions, and not busy, the first 02ae read places 153 bytes only in corresponding fields of model RAM.
- Field selection, order, single-byte read leases, and bounds are checked. Existing 4 µs IREG readiness and I2C/FIFO/IRQ transport are used; the CPU reads with the original read function.
- The fixture records one application, 41 field starts, and 153 byte reads. Values and checksum/provenance are retained in plan/capture. Other RAM, power-save time, and bootstrapping state are preserved.
- Device reset initializes the new read state. Invalid hex/size, incomplete prerequisites, skipped fields, duplicate selection, and overread are rejected.
- Support is limited to this initialization getter. Arbitrary-order GAF APIs, bias/parameter writes, GAF on-demand calculation, FIFO, and sensor fusion are outside this change's scope.

`runtime_enabled=false` in research JSON is preserved as the inactive research-input record created in bw349. This run uses a separate `--gaf-defaults` selection to add board parameters. The file's existence does not automatically apply it; actual selection follows capture `imu_gaf_selected`.

## Actual execution and memory verification

| Item | Result confirmed in all three images |
| --- | --- |
| Previous boundary | `7c02ae` address selection, no getter data received |
| New getter | one profile application, 41 fields, 153 bytes, zero remaining |
| Next boundary | `7c077400` first SRAM0774 magnetometer-bias write, strictly rejected before application |
| Current task | actual linked `sensor_hub`, 29 active tasks |
| CPU buffer | unique 168-byte GAF structure in current task stack; field values and constants 5000/2500 match |
| Original caller overwrites | run_spherical 1, pdr_us 20000, mag_dt_us 40000 |

The caller's mag interval was connected to actual R6 saved by the callee and original branches. Offset 8 was not assumed 0 based on the old temporary variable name `gyro`. Original initializer LR, exact calibration call/Thumb LR, HAL prologue/return, slave 69 and length 4 descriptor on stack, and actual payload were compared together. This is not a test copying host-expected pixels or structure into guest RAM.

With the option off in the new model, the stock24 control exactly matched CPU observations and all selected events in the previous power-save capture. Reversing source component substitution matched the original capture's strict source, confirming no changes outside the IMU component. Original main hashes also matched extraction from the pinned bundle.

The first stock24 run expected a temporary bounded boundary but reached the actual strict boundary: execution passed while semantic judgment failed. The original capture was not changed; it was audited against the actual boundary contract. Stock23/CFW ran with the final contract. This failure is neither hidden nor reclassified as a new successful run.

## Checks and failure history

- 2,108 new/inherited unit checks and 2,108 frozen-source checks passed. This is not a count of independent features or project completion.
- Three native runs, one option-off control, four saved audits, and three actual stack buffer/call/descriptor checks.
- Nine field/LR/payload mutations were rejected. Three controls changing only undefined structure padding were allowed, avoiding making padding 0 a success condition.
- The first auditor missed mutation of LR's Thumb bit. It was corrected to check the exact original call site and Thumb LR and passed the same mutation control. The initial script was preserved.
- Four planner checks covered another project root, preservation of existing output, bootstrap conflicts, and rejection of a mutated verification profile.
- The first unit run failed on earlier observer capacity. The next red with `--extended-observer` failed on the absent new class and turned green after implementation. The initial failure involving changed observation policy is not counted as model execution success.

Private assets: `simulator/imu-gaf-parameters-main-01/{stock24,stock23,cfw}`, `imu-gaf-parameters-off-01`, `imu-gaf-parameters-saved-audit-01/`, `imu-gaf-parameters-green-02`, `imu-gaf-parameters-frozen-unit-01`, `imu-gaf-planner-preflight-01`, `imu-gaf-parameters-verification-01/manifest.json`. Earlier material and initial failures were not overwritten.

## Reproduction and next behavior

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/prepare_imu_ireg_candidate.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-private-plan.json> --gaf-defaults

"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/run_native_candidate.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-private-plan.json> <new-private-capture> --case stock24
```

Existing inputs, source proof, and profile hash are required; preflight rejects missing or mutated files. Saved audit uses the same runner's `--audit-existing --audit-output <new-path>`. Integrated checker `verify.py --saved-only` revalidates saved captures using frozen model, profile, and dependencies without retrospective dependence on the current working tree. Unit checks pass simulator, new output path, and `--extended-observer` to `tools/verify_imu_gaf_parameters.py`.

Next connect mag-bias storage, clock variation, and GAF setter/service transactions as behavioral units. Full sensor initialization, normal app event processing, and natural UI remain incomplete. It is also unproven that IMU completion automatically starts the UI. Overall acceptance 3/16 and API first-screen checklist 3/6 remain. GPU optional sampling reference mode was deferred as a separate proposal and not implemented.
