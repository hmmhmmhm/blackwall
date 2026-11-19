# Original consumption contract and public defaults for ICM45608 GAF configuration

bw349 follow-up. The existing 153-byte getter corresponds to the public ICM45608 driver's **GAF configuration getter**. All 41 addresses, lengths, and member offsets in the 168-byte C structure matched across three originals. This is more specific identification evidence than the earlier generic “large IMU parameters.” It does not imply actual physical ROM values or a full driver-version match.

## Comparison with public source

The following from TDK `motion.arduino.ICM45608` commit `646f55a6ec119b59d9ebce47af660842b53e5506` were used:

- [inv_imu_edmp.c](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp.c): get/set GAF parameters and mag-bias setter.
- [inv_imu_edmp.h](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp.h): 168-byte GAF structure.
- [inv_imu_edmp_memmap.h](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp_memmap.h): 41 addresses, widths, and specified defaults.
- [calmag patch](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/edmp_prgm_ram_patch_calmag.h): public 189-byte image differs from the 125-byte image loaded by the original setter. Do not replace the original with the public patch.

Pinned manifest SHAs of existing C/H files were rechecked. Newly acquired memmap and patch were verified by Git blob SHA-1 and SHA-256. The original getter's 41 address/width/offset tuples were compared in each image; all 123 tuples matched. Field meanings are assigned on this correspondence, not extended to identity of ROM defaults or sensor-fusion algorithms.

## Correction of earlier names

The separate 12-byte helper in [first consumption analysis](imu-parameter-consumer-prefix.md) corresponds to public `inv_imu_edmp_set_gaf_mag_bias` in six addresses, input width, signed shift 5, and covariance by accuracy. Thus the input is magnetometer bias (Q16→Q11), and its mode corresponds to accuracy.

Caller buffer offset 4 is `pdr_us` and offset 8 is `mag_dt_us`. The `gyro` variable in earlier analysis and private probes was a temporary name for the original R6 0/1 control; **offset 8 must not be interpreted as gyro ODR or gyro data.** 0/40000 are values of the magnetometer interval field chosen by that caller. The higher-level origin of the R6 flag itself is not fully established.

## Full setter execution and failure controls

The entire original setter executed in all three images. Only bus register/SRAM leaves were replaced by ABI stubs; actual setter/helper instructions, branches, and bounded loops executed. Virtual register and RAM dictionaries are explicit test inputs. This is not execution of a separate EDMP processor or sensor fusion.

- Ready normal: two synthetic getter inputs × two ODR codes × two mag_dt_us values × two saved gyro accuracy words × three originals = 48 scenarios.
- Ready nonresponse: one per image, three total. The original performed three sections of 200,000 ready polls each, then returned `fffffffc`. The ready bit was not forced to success and timeout branches were not skipped.
- Normal cases had one ready poll each and returned 0. Input buffers and existing main SRAM were preserved.
- The getter's 41 fields/153 bytes appear unchanged from inputs in the setter's first write. This does not claim all addresses remain permanently equal after the entire setter; later helpers and loading write separate ranges.
- The original loads a 125-byte calmag image and thresholds 5000/2500. It writes temperature initialization word `feef0000` only when the saved gyro accuracy word is 0. This branch was controlled with zero and nonzero inputs.
- The device fixture has no delay callback. Loop counts therefore evidence original control flow, not measured actual elapsed time, Renode virtual time, or sensor processing time.

The first 500,000-instruction observation was still polling in nonresponse. It was preserved without counting it as completed timeout. The same call was executed with compressed repetition records and a larger finite instruction budget to confirm the actual error return.

## Candidate virtual initial state with provenance

The [explicit research profile](../../data/imu-gaf-default-profile.json) records the 153 bytes of 41 defaults documented by the memmap. It is not all zeros, and does not add structure padding or bytes the getter does not write as defaults. Caller overwrites of run_spherical/pdr_us/mag_dt_us are separate.

This profile was applied to getter output, original caller overwrites incorporated, and the result passed to the full setter. All three originals returned normally in 24 scenarios varying ODR, mag interval, and saved accuracy. This shows the CPU setter accepts that explicit input, not that EDMP performs sensor fusion or physical G2 provides identical initial values.

The profile retains `runtime_enabled=false` and `physical_g2_defaults_verified=false`. It was not applied to the Renode IMU model at bw349. The original/public calmag image difference remains a compatibility limitation. Even when connecting a future virtual profile to the model, record input provenance, application timing, and virtual services/unsupported algorithms; do not label it actual ROM values.

## Evidence and next work

The 51 full-setter and 24 public-default scenarios were rerun with frozen dependencies and report byte identity confirmed. They are distinct from the first prefix's 423 scenarios. Private assets are `simulator/imu-parameter-full-setter-01`, `imu-parameter-full-setter-frozen-01`, `imu-gaf-defaults-source-01`, and `imu-gaf-defaults-frozen-01`. Final verification status follows `imu-parameter-full-setter-01/verification-report.json`.

The next dependency is no longer unnamed 153 bytes but **source-pinned GAF initial state, magnetometer bias/accuracy, and GAF on-demand service completion contracts**. Follow-up work must define the scope for connecting this profile and original helper bus transactions to the natural main model and state which EDMP internal behavior is not calculated. Actual FIFO/samples and application behavior require separate verification.

The model, natural main baseline, and GPU were unchanged in this analysis. Overall 3/16 and API checklist 3/6 remain. The GPU optional reference profile awaits separate user design review.

Follow-up bw350 [natural main GAF getter](imu-gaf-default-getter.md) applied source-derived input under a separate option and verified the 153-byte read, actual caller buffer, and next 0774 write in all three originals. This is not promoted to physical ROM values, sensor fusion, or full initialization completion.
