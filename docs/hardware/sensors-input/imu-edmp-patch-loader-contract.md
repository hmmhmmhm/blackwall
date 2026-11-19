# IMU SRAM patch key and original loader function

bw-0334 identified the consumer of bw333's next stop, the SRAM `0048` read. **This address is an EDMP patch-table key, not a sensor sample or ODR value.** The original function transfers a dispatcher and feature image from the glasses CPU to internal IMU SRAM. No new Renode main run or internal IMU program execution has occurred yet.

## Actual calls and data

The loader entry was derived from the stack return in the current main capture: `555bcc` for stock 2.4 and `521d74` for stock 2.3 and pinned CFW. In current SRAM of all three images, the 25-byte dispatcher and 375-byte feature image to be transferred by the original were identical respectively. An ARM function embedded in the original firmware consumes these data; the data themselves were not executed as an ARM program.

| Purpose | IMU SRAM address | Length | Original contract |
| --- | --- | ---: | --- |
| Patch key lookup/set | `0048` | 4 bytes | Expected word `801570f1`, little-endian |
| Dispatcher load | `1580` | 25 bytes | Load only when key is 0 |
| Feature image load | `1600` | 375 bytes | Always request after key decision |

- If the key is 0, transfer dispatcher → key → feature image.
- If the key is expected, skip dispatcher and key writes but transfer the feature image again.
- For any other key, set error `ffffffff`, but subsequently request the 375-byte feature-image write and set usecase output to 0. The function does not immediately fail-stop.
- Read/write errors accumulate. The key mismatch branch overwrites the existing accumulated status with `ffffffff`. The caller must not judge success from the output byte alone.

## Public source and version differences

The patch key, conditional branches, and dispatcher correspond to `inv_imu_edmp_b2s_init_over_sif` in TDK pinned commit `646f55a6ec119b59d9ebce47af660842b53e5506`'s [extended features implementation](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp_extended_features.c). This supports identifying a B2S loader path. The function name was not established by physical behavior or independent symbols.

All 25 dispatcher bytes match the public image. However, the public B2S image is **1,310 bytes, destination `1000`**, while original main uses **375 bytes, destination `1600`**. Do not substitute the latest public B2S image for original data. The precise SDK release or algorithm version explaining this difference has not been identified.

Original dispatcher SHA-256 is `86e12e2483301114273ba809c1de6dbe11491c97e121f60ac6e8ef69472f98f8`; original 375-byte image SHA-256 is `16e4e9a482563c57ff82bec369464e0094d4a92140840edcaee738e201615ba7`. Payload contents remain outside Git.

Six public C/H, dispatcher, image, and definition files were verified by canonical Git tree blob SHA and SHA-256. Original files and notices were preserved unchanged and not replaced with IMU material for another model.

## Verification scope

`tools/inspect_imu_edmp_patch.py` checks bw333 manifest capture hashes, actual return/BL, original literals, and SRAM buffers. Instructions and branches inside the original loader execute as Thumb with Unicorn Cortex-M7 configuration. The two SRAM read/write callees are ABI stubs for collecting requests and returning explicit errors; this is not a test executing actual BLE/I2C, M55 main, or the IMU dedicated processor.

**48 conditions** were checked: three images × four keys (`0`, expected key, `1`, `ffffffff`) × two read states × two write states. Full addresses, lengths, and payloads of actual requests were compared to the original, and return status, output byte, and neighboring-byte preservation were checked. A write requested despite an error is distinct from a write applied to an actual device. This test collects requests and does not claim actual device application.

Two artifacts, report and inspector, from a frozen rerun are byte-identical. 482 Python sources were pinned and syntax-checked; hashes of 11 existing peripherals/observers were unchanged. There was no new native main run. bw333 service clear making model RAM `0048` zero is confirmed model behavior, but does not verify whether the actual IMU ROM decimation service preserves that address.

Private evidence is in `~/Library/Application Support/Blackwall/simulator/imu-edmp-patch-source-02/`, `imu-edmp-patch-source-frozen-01/`, `imu-edmp-patch-research-01/`, and `imu-edmp-patch-verification-01/manifest.json`.

## Next connection

Instead of a new arbitrary set of ROM defaults, read saved state of existing IMU model RAM and store the dispatcher/key/375-byte image sent by the original unchanged. Verify indirect sequential byte read/write cursor and range, and rejection of invalid lengths, images, and addresses before state changes. Distinguish already loaded keys, conflicting keys, and incomplete transfers. This is separate from implementing dedicated EDMP ISA execution.

After connection, resume natural original main execution to check feature parameters, external ODR, and FIFO boundaries, then continue toward a nonzero main frame/viewer. The current integrated boundary remains bw333's `7c0048`. Overall scope v2 remains **13/29 = 44.8%**. Full boot, application loop, integrated screen, physical sensor, and physical-device recovery remain incomplete.
