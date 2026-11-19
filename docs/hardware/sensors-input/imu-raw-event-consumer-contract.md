# Original IMU raw sample consumption contract

bw461. Independently of normal GAF research, the actual E12 sample consumer was found. **The original ARM callback was confirmed to receive accelerometer/gyroscope events and record raw values, calibrated floating values, time, and buffer index.** This is isolated Cortex-M7 testing; FIFO bus/IRQ → natural M55 main remains unconnected. E12 and overall 10/16=62.5% remain.

## Original function identification

Stock 2.4 callback is `0x4c4c6c`; stock 2.3/Faceclaw is `0x4b95b0`. A `DataParser` error-string reference and callback pointer `0x4c4c6d` were found in stock 2.4. Initialization at `0x4c22d8` loads that pointer and the next instruction stores it at +0x18 in a device-related structure. A string alone does not fully establish the FIFO bus path.

The callback uses a 20-slot × 112-byte sample area and a 12-byte header. Output addresses are stock 2.4 `0x20066640`, old2 `0x20066650`. It processes samples when index is less than 20; tested index 19 wraps to 0 after writing. Actual error handling/logging for index 20 or above was not in this run set.

## Executed contract

| Item | Input/observation |
| --- | --- |
| Input | Synthetic 80-byte event; accel/gyro bits 0/1 in byte 0, three signed16 axes each at +6/+12 |
| Sample area | Synthetic sentinel and header explicitly prepared; not treated as naturally initialized output buffer |
| Time | Uses selected period in original SRAM divided by 1000 and header base time/index difference |
| Accelerometer | Preserve three raw axes; convert `8×raw-bias` signed32→float32 then divide by 65536 |
| Gyroscope | Preserve three raw axes; convert `4000×raw-bias` the same way |
| Sample flags | Preserve existing upper bits and OR selected two bits; preserve raw/float areas for absent samples |
| Lifetime | Original callback return, SP restoration, unchanged input, full SRAM preservation outside expected changes |

Units were not independently verified here. Numeric representation and code transformations were confirmed, not actual g/dps, physical calibration accuracy, or sensor fusion. Period was 10000 µs read from the existing snapshot, not verified physical sampling timing.

32 runs per original (four axis inputs × four flags 0/1/2/3 × two indices 0/19), 96 across three originals. Axis inputs included -32768/32767, negative, zero, and asymmetric values. Even with flags 0, time/index advance and sample area is preserved. Flags other than accelerometer/gyroscope and GAF results are outside this contract.

One additional hook-on/off pair per original had exact full SRAM, test WORK, and R0–R12/SP/LR/PC. Final total is 102 runs. Original callback and actual memset/numeric helpers executed without callee stubs or forced PC/returns/branches during execution. Entry arguments, return sentinel, and output area are isolated test fixtures. Observer noninterference for all FPU registers was not separately established.

The first call failed before ARM execution because Unicorn rejected a bytearray argument; it ran after conversion to bytes. Initial report aggregate constant 198 was corrected to actual 96+6=102, preserving the original report. This count is not added to feature progress.

## Remaining FIFO connection

The [advanced driver](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_driver_advanced.c#L851) from existing pinned TDK ICM45608 commit `646f55a6ec119b59d9ebce47af660842b53e5506` was newly read and compared against saved Git tree blob/SHA256. It separates FIFO count/data reads, frame interpretation, and `sensor_event_cb` invocation. Its structure/function addresses are not assumed identical to the G2 original.

Next trace the callback's actual indirect caller in G2 original and pin FIFO count/data read, frame size, endianness, and IRQ/task consumption contracts. Do not inject this synthetic event as a substitute for FIFO bytes or normal fusion results. Natural main sensor consumption cannot be claimed complete until required normal GAF initialization is resolved.

Private `simulator/imu-fifo-consumer-contract-01/` preserves probe/report, three observation paths, original advanced source, preparation error record, and manifest. Original main was reverified from the verified bundle. No model changes, physical access, subagents, or external publication.
