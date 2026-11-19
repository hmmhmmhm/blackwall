# WOM threshold and control configuration

bw-0337 connected original main's WOM X/Y/Z configuration and enable call to the virtual IMU. This scope is **storage of three threshold bytes and two control-register RMWs**. Physical motion detection, IRQ, and power savings were neither implemented nor verified.

## Original calls

Stock 2.4 configuration function is `551f0e`, enable function `551f7c`. Call targets were derived from current return/BL in all three images. The caller passes X/Y/Z `2/2/2` and stack arguments mode `0`, duration `1`. These are not converted to physical units, sensitivity, or time.

The configuration function transfers the low bytes of the three arguments to `a27e..a280`. It then reads `23`, sets bit 3, and replaces bit 2 and bits 0..1 with arguments. Original enable function rereads `23` and sets only bit 4. Pinned TDK regmap `TMST_WOM_CONFIG` defines bits 0..1 as `wom_int_dur`, bit 2 `wom_int_mode`, bit 3 `wom_mode`, and bit 4 `wom_en`. Upper timestamp-related fields and others retain original values.

Error statuses accumulate by OR, but original functions continue requesting subsequent reads/writes. Bus errors do not guarantee automatic rollback or immediate stop. This standalone test checks requests and return status, not actual chip application on error.

## Explicit model

New `BlackwallImuWomConfiguration` is created only with `womConfigurationHex` and requires the preceding B2S parameter stage. Inputs are initial X/Y/Z bytes followed by initial control byte. Default test fixture `a5b6c7c3` is not a physical reset value.

Thresholds are written once in order to three addresses; control may update only after a read lease. The first RMW accepts only preservation of upper four bits and bit 3 set. The second accepts only existing control OR `10`. Invalid order, fields, or writes without reads are rejected before application. Repeated reconfiguration after the preliminary phase is not yet supported.

Actual original runs confirmed `a27e/a27f/a280=02/02/02`, control `c3 → c9 → d9`. Threshold continuation uses existing IREG address cursor, separated from other IMU submodel write cursors. No fake sensor events or CPU returns are supplied.

## Verification

- 504 original ARM wrapper and 504 frozen-source conditions. Three images ran one enable function and configuration mode 4 × duration 5 with four initial controls × two bus statuses. Low bytes `2/3/4` of threshold arguments `2/103/204` were also confirmed in transfer.
- This standalone analysis substitutes register read/write callees with ABI stubs. Internal ARM instructions/branches are original, using Thumb under Unicorn Cortex-M7 configuration; it is distinct from natural Renode M55 main. Frozen report/inspector artifacts are byte-identical.
- Three original mains (stock 2.4, 2.3, pinned CFW) confirmed three threshold writes, two control reads and writes each, and final `020202d9`. Previous B2S 20 bytes and prefix remained.
- Next request `7c0040` selects address for IMU SRAM `0040` read. Descriptor address 69, write length 3, and payload derived from actual HAL prologue/caller were confirmed in each capture's SRAM. Data at that address were not received.
- Disabled control exactly matched prior bw336 CPU state and all selected events. Four native runs and four saved reaudits had no event loss.
- 1,612 unit and 1,612 frozen-source checks include 1,565 existing checks. They cover threshold order, read leases, upper-bit preservation, mode/duration combinations, rejection of changes outside enable bit, rejection of extra phases, and reset.
- Ten existing peripheral/observer hashes unchanged; one IMU model changed. 487 Python sources were pinned and syntax-checked, not counted as full functional tests. Previous B2S planner matched except current IMU SHA.

Baseline import failure without the new class was confirmed first. The first native provisional semantic contract failed because it differed from the actual strict boundary; the capture was separately audited against the final strict contract without modification. Firmware bytes, CPU branches/returns, and observers were unchanged.

## Next scope and evidence

Original `55408e` corresponds to a power-save getter reading four bytes of SRAM `40` and bit 2 of `2a`. The caller also has a WOM reconfiguration path (threshold `0d`) depending on a separate flag. Completion of this first configuration is not expanded to support for every reconfiguration lifecycle. Next examine power-save parameters, conditional WOM reconfiguration, and associated enable settings together. Actual ROM service RAM initial values remain unverified.

Code is in `tools/inspect_imu_wom.py`, `tools/verify_imu_wom.py`, `tools/renode-imu-identity.cs`, and shared planner `tools/prepare_imu_ireg_candidate.py`. Proprietary inputs, SRAM, and logs are preserved outside Git at `~/Library/Application Support/Blackwall/simulator/imu-wom-main-01/`, `imu-wom-saved-audit-01/`, `imu-wom-source-01/`, and `imu-wom-verification-01/manifest.json`.

Then continue external ODR/FIFO and nonzero main frame/viewer. Overall scope v2 remains **13/29 = 44.8%**. Full boot, app loop, integrated screen, physical sensor, and physical-device recovery remain incomplete.
