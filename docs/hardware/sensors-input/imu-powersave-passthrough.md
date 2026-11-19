# Explicit ROM result and value preservation for power-save parameters

bw-0338 analyzed original main's power-save getter/setter and conditional WOM path and connected the current default path to the virtual IMU. **The actual IMU ROM initial value at `0040` remains unknown.** The model supplies an explicit nonzero test value and verifies that original code writes it back unchanged. This is not verification of physical ROM defaults or power savings.

## Original data flow

Stock 2.4 getter/setter are `55408e/554162`. Calls were bound from current stack return/BL in each image. The getter copies four bytes from SRAM `0040` to the front of the caller buffer and puts `2a` bit 2 in the request-flag position.

Actual global flags in all three original mains are power-save `0`, B2S `1`. The caller does not calculate or overwrite the time word; it changes only the request flag to 0 and passes it to the setter. This path does not reconfigure WOM: the setter clears `2a` bit 2 and writes the received time word unchanged to SRAM `0040`. Existing WOM is retained.

The entire setter was examined. Other branches occur after the first return point, so analysis only through a single return was insufficient.

- If core is off or request flag is 0, update control bit 2 first, then write the time word.
- If core is on, request is 1, and existing bit 2 is 0, write the time word first, then set bit 2.
- If core and existing bit 2 are on and 1 is requested again, return `ffffffff` without writing.

Bus statuses accumulate by OR; in other branches subsequent writes are requested even on errors. This analysis does not prove what values a physical chip applies on error or whether it rolls back.

Other caller flag combinations were checked separately in original ARM. With power-save flag 1, WOM is reconfigured to `0d/0d/0d`, mode 1/duration 0, and enabled. If both power-save and B2S are 0, WOM is disabled. These alternate paths are source-supported but outside this natural main/model support scope.

## Explicit model and limits

`BlackwallImuPowerSave` is created only when `powerSaveTimeHex` is supplied. On first `0040` address selection after existing EDMP service and WOM stages, it places these four bytes in the same model RAM. Application count is recorded diagnostically; it is not classified as firmware-written or verified ROM initialization. No hidden zero default is supplied.

It then uses the first IREG readiness delay and sequential-read cursor. Only two control reads and a bit-2 disable write in the current source flow are supported; changes to other bits are rejected. The time value is accepted only when the same four bytes read are written in order. Other values, addresses, orders, and writes without initialization are rejected before application. This is not a general power-save enable or complete reconfiguration API model.

Control RMW is applied to the existing EDMP bank. Natural main changed `8f → 8b`, preserving other bits. The model RAM time word remained unchanged for `78563412` (little-endian `12345678`) and control `f0debc9a` (`9abcdef0`). Both are test inputs, not physical device recommendations or time units. Physical sensor/DMP execution, WOM events, and power consumption are not simulated.

## Verification

- 396 original get/set/caller conditions and 396 frozen-source conditions. Across three images these covered three time values, two statuses, six getter enables, six setter enables × two requests, and four caller power/B2S flag combinations. Time preservation, control order, write rejection, error returns, output neighboring bytes, and caller SP/return status were checked.
- Wrapper register/SRAM callees and caller WOM/power setter callees are explicit ABI stubs. Standalone Thumb analysis under Unicorn Cortex-M7 configuration is distinct from natural Renode M55 main. Frozen report and inspector artifacts are byte-identical.
- Three original mains confirmed one profile application, four bytes each read/written for time, two control reads/one write, and bit 2 disabled. An additional native run with another nonzero time reached the same behavior and next boundary.
- Next request is `7c02ae`, address selection for SRAM `02ae` read. Descriptor address 69, length 3, write, and payload derived from HAL prologue/caller were confirmed in SRAM of four active captures. Data at that address were neither supplied nor received.
- Disabled control exactly matched bw337 CPU state and all selected events. Final five native runs and five saved reaudits had no event loss.
- 1,683 unit checks and 1,683 frozen-source checks include 1,612 existing checks and service prerequisite checks. They covered explicit profile application; nonzero/zero/all-one time; disabled-bit preservation; rejection of write before read, different time, order, and end-boundary violations; neighboring RAM preservation; and reset.
- Ten existing peripherals/observers retained hashes, and one IMU model changed. 489 Python sources were pinned and syntax-checked; syntax checks are not counted as full functional tests. The previous WOM planner matched except for current IMU SHA.

Baseline import failure without the new class was first confirmed. The first native provisional semantic contract failed because it differed from the actual strict boundary; the capture was not changed and was separately audited under the final strict contract. Firmware bytes, CPU branches, returns, and observers were unchanged.

## Next scope

Next identify the original consumer reading `02ae` and remaining sensor initialization flow. Trace whether ROM values affect branches, calculations, or algorithm results; do not unconditionally return 0. Also check the dependency between integrated UI startup and sensor initialization, rather than substituting individual register tracing for the overall screen goal. Then continue external ODR/FIFO and nonzero main frame/viewer.

Code is in `tools/inspect_imu_powersave.py`, `tools/verify_imu_powersave.py`, `tools/renode-imu-identity.cs`, and shared planner `tools/prepare_imu_ireg_candidate.py`. Proprietary inputs, SRAM, and logs are preserved outside Git at `~/Library/Application Support/Blackwall/simulator/imu-powersave-main-01/`, `imu-powersave-alternate-01/`, `imu-powersave-saved-audit-01/`, `imu-powersave-source-02/`, and `imu-powersave-verification-01/manifest.json`.

Overall scope v2 remains **13/29 = 44.8%**. Full boot, app loop, integrated screen, physical sensor, and device recovery remain incomplete.
