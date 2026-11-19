# IMU ODR and accelerometer filter configuration path

bw-0331 connects configuration executed after original main's magnetometer initialization. ARM instructions from stock 2.4, 2.3, and pinned Faceclaw CFW execute on Renode M55 without modifying firmware bytes, branches, or returns or forcing the CPU path forward. No physical device was used.

## Confirmed execution scope

Actual configuration globals in the three images are `02 09 09`, with gyro enable flag `0`. The natural main path executes APEX ODR value `2`, accelerometer ODR value `9`, accelerometer clock selection, filter, and full-scale configuration. These are original enum codes, not converted to physical Hz or measured performance.

Actual write sequence is `27 → 1b → a258 → a581 → a583 → 1b`. Initial fixture `a5b6c7c8e9faab9c` becomes `a2b9c7d8e0f8ab9c`; control fixture `3c4d5e6f708192a3` becomes `3a395e7f708092a3`. The eight bytes are ordered `27,1b,1c,a258,a581,a583,a4aa,a4ac`. These are explicit simulator inputs, not physical reset values. The final full-scale write of the default fixture writes the same value; the control fixture changes value.

The register name `DMP_EXT_SEN_ODR_CFG` alone does not establish completed external-sensor ODR configuration. This run changes only APEX configuration in low three bits of `27`; external ODR bits 3..5 were neither supported nor executed. Gyro ODR, filter, and full-scale were skipped under the current flag, so standalone original-function tests are distinct from natural main execution.

The next stop is a four-byte HAL transaction `7c a2 4f 00` attempting to write `00` to EDMP initialization register `EDMP_PRGRM_IRQ0_0` (`a24f`). FIFO and subsequent external ODR configuration remain after that initialization. Unsupported writes are rejected by the peripheral model before application.

## Model and verification

The ODR model allows only permitted single-field writes following reads; indirect registers use the existing IREG transport timing model. `a258` provides storage only. Physical clock, sensor sample generation, DSP filters, and frequency response were neither implemented nor verified. Observers match bw330; no new hook was added.

- Standalone original ARM RMW tests: three images, ten fields, 256 initial values, two boundary values, 15,360 conditions total. Frozen-source rerun report and inspector are byte-identical.
- 244 model unit checks and 244 frozen-source checks. Pinned hashes/syntax checks for 479 Python sources are not a count of full functional tests.
- Five natural M55 runs: three original images, one initial-value control, one model-disabled control; five saved reaudits. Four active runs check the next HAL descriptor in SRAM and actual call frames.
- Active runs retain six configuration reads and six writes, 13 existing magnetometer transactions, and one ID lookup. Disabled control exactly matches bw330 CPU state and all selected events. No events lost.
- Ten existing peripherals/observers retained hashes; only one IMU model changed. Three existing planner paths were preserved.

The first red run timed out and is not used as evidence of missing functionality. After confirming no related process remained from the interrupted run, the candidate was preserved separately, the previous model's missing-new-class failure reproduced, and the candidate restored to confirm green. This is not described as red/green success from the initial run. Interrupted source/unit runs are excluded from success counts. The first 2.4 capture was valid execution but failed the provisional semantic boundary; it was judged by a separate final semantic-contract audit without changing the original capture.

## Remaining work and evidence

Investigate actual call scope and conditions for EDMP IRQ/reset/RAM initialization as a unit, then resume external ODR/FIFO configuration. Do not force the disabled gyro state to create natural-execution success. Then verify nonzero integrated main frames and viewer connection.

Proprietary images, SRAM, logs, and hash manifest are outside Git at `~/Library/Application Support/Blackwall/simulator/imu-odr-verification-01/`. Standalone original ARM tests are in `imu-odr-source-02`, native captures in `imu-odr-main-01`, `imu-odr-alternate-01`, and `imu-odr-control-01`, and separate audit in `imu-odr-saved-audit-01`.

Overall progress remains scope v2 **13/29 = 44.8%**. Progress on this partial path is not completion of full boot, app loop, integrated UI, physical sensor, or recovery verification. bw-0331's external ODR/FIFO goals carry forward.
