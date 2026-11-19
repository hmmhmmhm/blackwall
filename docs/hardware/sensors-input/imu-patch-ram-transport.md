# SRAM transfer and stored-data reads for original EDMP patch

bw-0335 connected the [patch key contract](imu-edmp-patch-loader-contract.md) to existing IMU model RAM. It confirms the path where original ARM main transfers a 25-byte dispatcher, 4-byte key, and 375-byte feature image and reads parameters from stored data. **Storing an opaque EDMP program differs from executing its dedicated processor's instructions.** This change covers transfer, storage, and reads, not EDMP ISA or B2S algorithm execution.

## Implementation

`BlackwallImuPatchRam` activates only after two EDMP service completions. It uses the same byte array as `BlackwallImuEdmpService`, without an independent RAM copy. The marker is read from existing model `0048..004b`. In the default path this region is 0 due to the earlier explicit RAM clear. This does not verify that actual ROM decimation preserves that address.

The read cursor advances per byte after existing 4 µs IREG readiness on first address selection. Only the four-byte marker and completely loaded feature image `1600..1776` are readable. A new address selection may replace the remaining cursor of a prior read; reads beyond region ends are not provided. Arbitrary 0 is not returned for other RAM or ROM addresses.

Writes check original dispatcher/key/feature image order, addresses, and expected bytes. Invalid bytes or order are rejected before application. Already received partial data remain but are not marked fully loaded. Expected feature-image data are extracted from actual SRAM contents of pinned captures, SHA-256 checked, and placed only in private plans. Proprietary payload is not put in Git source.

Existing-key and conflicting-key paths also follow original behavior. Even with a conflicting key the original function requests the feature-image write, so the model permits that request without marking normal load state. Do not describe this as fail-stop or atomic installation rollback. Key override is an explicit unit-control fixture, unused in the default native path.

## Verification

- Three originals (stock 2.4, 2.3, pinned CFW): dispatcher 25, key 4, feature 375, total 404 bytes loaded. Four marker bytes and 20 stored parameter bytes read. Two existing EDMP service completions and prior prefix retained.
- Next request is `7c16185e`, a parameter change beginning `1618=5e`. It is unsupported and stops strictly before application. Address `69`, write length 4, and payload in descriptor derived from original HAL prologue/caller were confirmed in SRAM.
- Disabled control exactly matches bw333 CPU state and all selected events. Four final native runs and four saved reaudits were confirmed. One preliminary native with a narrower initial read range is preserved separately and excluded from this count. No observation events were lost.
- 1,539 unit checks and 1,539 frozen-source checks, cumulative including 333 existing checks. They cover order/byte rejection, partial load, early key-write rejection, region-boundary preservation, existing/conflicting keys, sequential stored-data read, address reselection, end boundary, and reset.
- Ten existing peripheral/observer hashes match; only one IMU model changed. 483 Python sources were pinned and syntax-checked; syntax checks are not full functional tests. Previous service planner matches except current IMU SHA.

Original code, CPU branches/returns, and firmware bytes were unchanged. No new PC hook or observer-capacity change. Host CPU code running original is Renode M55; bw334's 48 ARM wrapper conditions are separate pinned evidence with bus callees substituted.

Baseline import failure without the new class was confirmed first. The first candidate completed patch transfer but stopped at next `1618` read. Because this address lies within the just-stored image, marker-only reads were extended to sequential stored-region reads and additional unit checks performed. Preliminary candidate and first frozen copy are not used as final-code evidence. The final 2.4 run's provisional semantic-boundary failure was also preserved and separately audited under final strict contract without changing capture.

## Evidence and next scope

Code is in `tools/renode-imu-identity.cs`, `tools/verify_imu_patch_ram.py`, and shared planner `tools/prepare_imu_ireg_candidate.py`. Private evidence is preserved under `~/Library/Application Support/Blackwall/simulator/`.

- `imu-patch-ram-main-02/{stock24,stock23,cfw}`: final original runs.
- `imu-patch-ram-control-01`, `imu-patch-ram-saved-audit-01`: disabled control and audit.
- `imu-patch-ram-main-01/stock24`: preliminary run before read extension.
- `imu-patch-ram-verification-02/manifest.json`: final source, execution, and verification hashes.

Next analyze and support original B2S parameter structure and field writes beginning at `1618` together. Do not apply the latest public image layout to the original 375-byte image. Then continue external ODR/FIFO configuration and nonzero main frame/viewer. Overall scope v2 remains **13/29 = 44.8%**. Full boot, app loop, integrated screen, physical sensor, and physical-device recovery remain incomplete.
