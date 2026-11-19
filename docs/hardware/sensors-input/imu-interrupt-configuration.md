# IMU INT1 configuration and subsequent power/ODR path

bw-0326. INT1 pin configuration after [FIFO/FSYNC state initialization](imu-advanced-tag-initialization.md) was connected, and subsequent prerequisites and power/ODR fields identified in the original. This does not verify interrupt generation, actual power behavior, or sampling.

## Actual caller and modification scope

Current HAL frames, saved read-reg returns, setter prologues, and upper caller BLs were linked across three originals. The caller passes INT1 selector 0 and three bytes `{1,0,0}`. The setter reads register 18 INT1_CONFIG2 and changes only the low three polarity/mode/drive bits, preserving the upper five.

`tools/inspect_imu_configuration.py` checks actual caller/frame and original/audit file pins. Per original image it checks five selectors, 256 initial bytes × eight configurations for RMW preparation, one read error, and four status-OR cases after write. Total: 6,174 independent ARM fragments across three images. INT2 selector 1 → register 58 and invalid-selector error returns are source tests, not implementation of peer INT2 functionality.

Even if read returns an error, original code prepares RMW write arguments and ORs read/write statuses for return. Do not claim verification of actual bus errors, invalid buffers, or complete caller recovery. Fragments use explicit fixtures before callee entry or after return; natural main execution is separate.

## Limited register model

`int1Config2` in `tools/renode-imu-identity.cs` defaults to -1 (unsupported). Only after explicit FSYNC bootstrap does it support one register 18 read and low-three-bit write. Upper-bit changes to the existing byte, writes before read, reads of another length, and other INT banks are rejected. It does not drive the controller or an actual GPIO line.

Initial a6 and control 5b are simulation inputs for testing reserved-bit preservation. They are not claimed as physically valid reserved-bit combinations or stock reset values. The byte requested by the original CPU is latched; the model does not force the result to 1. `verify_imu_configuration.py` runs 86 checks including existing checks. The missing-constructor red was preserved.

The shared `prepare_imu_ireg_candidate.py` option `--int1-config2` is used. Existing IREG and FSYNC plans matched previous plans except for explicitly changing the current model SHA. No new native runner was created.

## Original M55 results

| Input | Initial register 18 | Value saved by original write | Next unsupported request |
| --- | --- | --- | --- |
| Stock 2.4 | a6 | a1 | register 2a select |
| Stock 2.3 | a6 | a1 | register 2a select |
| Faceclaw | a6 | a1 | register 2a select |
| Stock 2.4 control | 5b | 59 | Same next boundary |

Each run confirmed one INT1 read/write, 19 successful I²C finishes, and seven received bytes. The new request's actual HAL descriptor also matched address 69 and register 2a selection. Earlier event prefixes were preserved. The disabled control exactly matched bw325 FSYNC-only full CPU state and all observed events.

There are five valid native runs, five saved audits, and four actual pin-state checks. The initial provisional boundary contract failure was preserved and verified by a separate audit changing only its own capture plan's semantic contract. Original ARM instructions/branches/returns and observers were unchanged.

## Prerequisites and actual power/ODR locations

Next register 2a is EDMP_APEX_EN1. The actual first callee prepares an RMW clearing bit 4 GAF enable. It was compared with `inv_imu_edmp_disable_gaf` in the official [pinned EDMP source](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp.c).

Additional source was downloaded to separate private research assets without changing the existing TDK source folder, and canonical Git blob SHA1/SHA256 were verified. Repository LICENSE is BSD-3-Clause; the file's InvenSense copyright/permission/as-is header was preserved unchanged. File-specific headers are not replaced by arbitrary SPDX names.

The original port routine accumulates statuses from five prerequisite calls and has an error-0 gate. After that gate it requests accel/gyro mode 0. Fields compared between original setter and pinned SDK are:

| Role | IMU register | Changed field | Current evidence |
| --- | --- | --- | --- |
| accel mode | PWR_MGMT0 `10` | bits 0..1 | Original setter and upper caller mode 0 confirmed |
| gyro mode | PWR_MGMT0 `10` | bits 2..3 | Original setter and upper caller mode 0 confirmed |
| accel ODR | ACCEL_CONFIG0 `1b` | bits 0..3 | Original setter field confirmed; actual requested value unknown |
| gyro ODR | GYRO_CONFIG0 `1c` | bits 0..3 | Original setter field confirmed; actual requested value unknown |

This path was statically confirmed in three versions, not yet power/ODR configuration executed by natural main. Full side effects of other prerequisite calls and EDMP idle conditions remain unverified. The first flow check failed by counting an error-logging call among prerequisites; it was corrected to scope before the error-0 gate. Failed code and records were preserved.

## Verification assets and next work

All report values matched between 86 unit and 86 frozen checks. The 6,174 original and 6,174 frozen fragments passed; source report/inspector artifacts were byte-identical. 469 Python sources were byte-identical to frozen source and passed syntax checks. This is not functional testing of all 469 tools.

Frozen unit/source tests, capture/audit, and actual state/subsequent-flow checks are preserved in private `simulator/imu-configuration-verification-01/manifest.json`. Nine existing peripheral models were unchanged; only one IMU peer was extended.

Next verify EDMP/GAF deactivation as a unit and idle/error conventions, then connect power/ODR after passing the confirmed gate. Do not skip prerequisites or fill unknown values with 0. Then continue nonzero main draw and framebuffer/576×288 viewer.

Overall 13/29=44.8%, scope v2. Goals remain web installation, Faceclaw CFW, recovery boot, integrated simulator, and screen. Actual sensor interrupt/sample, full boot/UI, and device recovery remain incomplete; no physical connection, installation, or persistent writes.
