# WHO_AM_I Failure Path and Independent INT1 Access

Partial verification as of bw-0357. With virtual WHO_AM_I set to 0, device-check failure was run from main reset for original stock 2.4/2.3/Faceclaw. Even after the original driver returned `-1`, the upper code attempted INT1 configuration and EDMP disable. Investigation is deferred because the upper initializer and wrapper returns and app startup have not yet been reached. The subsequent [explicit initial indirect readiness profile](imu-initial-indirect-profile.md) is an optional assumption and does not change the default unknown state.

## Distinguishing error types

The current IOM missing-peer/IllegalCommand was not used as an actual I²C NACK. This input is **an identity-byte mismatch in the selected virtual ICM**, not evidence of reproducing a bus NACK or physical failure. Only the existing identity fixture changed; original main, branches, return values, and TCB were not patched.

Four PC observation points were added at the original device-check function return, reset entry, sensor initializer return, and upper wrapper return. The actual R0 is recorded at return points. In all three failures, the device check returned `FFFFFFFF`, with 0 reset entries/requests. The sensor initializer and wrapper return points were not observed. This natural main run does not claim final confirmation of the earlier source-only finding that the wrapper might conceal an error.

## Corrected model constraint

The first failure run stopped while attempting to read INT1_CONFIG2(18) after the device check because the model tied this explicit register to `FsyncReads>0`. The public TDK [INT1_CONFIG2 definition](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_regmap_le.h#L84) is an independent byte with 3 polarity/mode/drive bits and 5 reserved bits. Its model value is already explicit. There is no basis for treating the call order of one historical initialization path as a register access condition.

The condition was therefore changed to **an explicit value exists and soft reset is not in progress**. Unspecified default values and access during reset remain rejected. The read prerequisite, one-byte length, preservation of the upper 5 bits, and existing unsupported indirect/EDMP boundaries remain. This change does not permit other unknown registers or initialization as a whole.

Checks covered reads before reset/FSYNC for every initial value 0–255, RMW preservation, fixture restoration after host reset, and rejection while soft reset is in progress. The previous FSYNC prerequisite rejection test was replaced with a successful read test for the new contract. Before the change it failed on peer-write rejection; afterward 5,042 checks passed, including existing checks.

## Natural execution results

| Profile | Device check return | Reset | Subsequent behavior and stop |
| --- | --- | --- | --- |
| ID0, three originals | FFFFFFFF | No entry, 0 requests | 1 INT1 read and 1 write → 6 EDMP disable writes / 1 request → strict stop at unreset IPREG_MISC indirect selection `7ca297` |
| ID81, stock 2.4 control | 0 | 1 entry and 1 request | Existing bias/GAF 225-byte storage → strict stop at first GAF service `7c000402` |

No initial indirect state was supplied in this work. The failed ID path is not assumed to have performed reset, and IPREG_MISC readiness is not fabricated and returned. INT1 model usability outside the nominal path improved, but the full app lifecycle after failure was not verified.

Actual guest SRAM in the three failure captures showed the current `sensor_hub` task and 29 connected tasks. Main is byte-identical to each pinned original, and compiled strict source matches the previous source except for the one INT1 condition line. The same observation recipe was used for the three failures and nominal control. For the stock 2.4 nominal control, the earlier CPU report and full 3,670,016-byte SRAM match exactly, as does existing event content excluding the four new labels/sequences. This single-input control does not guarantee that all observers are unaffected.

## Preservation and reproduction

Paths below are relative to `~/Library/Application Support/Blackwall/simulator/` outside Git:

- `imu-identity-failure-main-01/stock24`: first capture, in which selection 18 was rejected under the previous FSYNC ordering constraint.
- `imu-independent-int1-red-01`, `imu-independent-int1-green-02`: 5,042 checks before and after the correction. The 4,017 checks in green-01 were an intermediate result before adding the 256-input checks.
- `imu-identity-failure-main-02/{stock24,stock23,cfw}`, `imu-identity-nominal-main-01/stock24`: four actual runs of the final model.
- `imu-identity-*-plan-02.json`: provisional semantic contracts at execution time. The three failures passed execution but failed the expected semantic boundary.
- `imu-identity-*-plan-03.json`, `imu-identity-failure-audit-01/`: four semantic audits updated to the actual strict boundary without changing run settings. These are not native reruns.
- `imu-identity-failure-research-01/{verification-report.json,frozen-verification-report.json,manifest.json}`: checks of tasks, originals, single-component change, failure/nominal control, and source/evidence hashes. Frozen check results are byte-identical.

The existing identity preparation tool was extended; no new per-register runner was created.

```sh
python3 tools/prepare_iom4_imu_candidate.py \
  "$HOME/Library/Application Support/Blackwall/simulator" <new-plan-json> \
  --current-startup --case stock24 --identity-byte 0

"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  "$HOME/Library/Application Support/Blackwall/simulator/imu-identity-failure-research-01/frozen/tools/verify_imu_identity_failure.py" \
  "$HOME/Library/Application Support/Blackwall/simulator" <new-verification-json>
```

ID81 is the nominal control using the same observations. The old WHOAMI-only path remains a separate pinned research path. Next, define a contract that can verify the initial indirect access state after failure and error accumulation/upper returns. NACK, GAF calculation, nominal initialization, and natural UI are not marked complete. Overall progress remains 4/16=25%, with API checklist 3/6; no physical access, installation, or permanent write occurred.
