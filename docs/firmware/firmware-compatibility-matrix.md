# Firmware Compatibility Matrix — 2026-11-10

Virtual verification update, 2026-11-17: the currently active scope is an emulator for CFW testing. In known virtual MRAM with stock 2.4 main + research-patched 2.4 boot, an original-main callback restored the complete boot footprint; the full 4 MiB original hash and new stock boot → main/frame were confirmed. **Compatibility is verified only in this pinned virtual profile**; hardware, case, physical left/right units, other versions, and natural OTA remain unverified. See [results and exact scope](../bootloader/main-driven-boot-restore-results.md). The physical-device assessments in the November 10 table below are not upgraded.

Verdicts: **verified compatible / source-supported, physically unverified / unknown / incompatible**. Upstream physical-device reports are separately identified in the evidence column. No combination has currently been verified on the user's device. The latest official Even distribution version has not been established either.

Initial product priority (November 10): native iPhone M0 was an initial proposal, with installation and stock restoration prioritized. Follow the [current roadmap](../research/safety-first-roadmap.md).

| Combination | G2 hardware | L/R main | Boot | Case | Software | Verdict and scope |
| --- | --- | --- | --- | --- | --- | --- |
| User-owned device | Revision unknown, model S211 | Official app combined display **2.4.0.24**; individual sides unconfirmed | Both sides unknown | Not displayed in app; actual version unknown | Installed official app **2.4.0** confirmed by user, build number unknown | **Unknown**; photos and user-reported versions alone do not establish flash compatibility. [Device information](../archive/device-inventory.md) |
| M0 Mock | Not required | Not required | Not required | Not required | SwiftUI + mock, proposed | Device compatibility not applicable. Xcode 27.2 confirmed; build/launch not run |
| Stock information probe | Unknown | Stock support in source; actual per-version reverification needed | Insufficient information on requirement | Not used | Faceclaw `70ec2a0`, `IosDeviceInfoProbe` | **Source-supported, physically unverified**. May store a bond |
| Faceclaw CFW | Device revision unspecified | Based on 2.3.0.24; actual values on both sides unknown | Bundle's 2.3.0.24-family boot | Bundle raw matches SHA required by case 1.2.57 | Faceclaw `70ec2a0` + g2flash `845f665`, contract /38 | **Source-supported, unverified on user's device**. 39 patches/hash identity confirmed |
| Faceclaw downgrade classification | Unknown | Classifies through 2.4.0.24 as `newer-stock-validated` | Separate recovery-boot mixing unconfirmed | Unknown | `firmware-compat.ts`, [author issue #56](https://github.com/jimrandomh/faceclaw/issues/56) | **Source-supported, unverified on user's device**. Author describes general Faceclaw downgrade support; not generalized to evidence for separate recovery combinations or all hardware |
| Boot-patch documented target | 5 | Main 2.4.0.24; per-side equivalence unverified | Exact SHA of stock 2.3.2.14 | 1.2.57 | Boot patch `6198d70`, wire 2 / RAM API 3 | **Source-supported, unverified on user's device**. Upstream reports partial right-side verification; full-main recovery unverified |
| 2.3.0.24 boot as patch input | Unknown | Irrelevant | SHA `52ed1c4d…` | Irrelevant | patch.py pinned-SHA check | **Incompatible**. Required SHA `22a2b98e…` and length both differ |
| Boot from official 2.4.0.24 bundle as patch input | Unknown | 2.4.0.24 bundle | SHA `ecb91896…`; identity with actual device unknown | Distributed raw matches existing case | Boot patch `6198d70` | **Incompatible input**. Rejected by actual patch-input check; main version alone does not establish a supported combination |
| Patched boot + current Faceclaw full OTA bundle | Revision 5 irrelevant | CFW 2.3.0.24 | Installed patched 2.3.2.14 | Case raw matches | Unmodified g2flash full transfer | **Incompatible deployment plan**. Transferring a different stock boot from the bundle risks losing the recovery patch. Mixed compatibility of main itself remains separately unknown |
| Patched boot + CFW main-only | Unknown | 2.3.0.24 CFW | Patched 2.3.2.14 | Assumed 1.2.57 | Unwritten combination | **Unknown**; arbitrary repackaging/installation not authorized |
| Future Blackwall firmware | Unknown | Undetermined | Undetermined | Undetermined | Capability contract undetermined | **Unknown**; design after need is established |
| Current AM-Guru WebFlasher + g2flash CFW | Unknown | /38 CFW | Unknown | Unknown | WebFlasher `2fcdb888` | **Unsupported under current deployment policy**: official-only. Default simultaneous two-side BLE path also does not match Blackwall procedures |
| SybilSight distribution + future Blackwall | Unknown | Unknown | Unknown | Unknown | Static inspection of distribution JS only | **Unknown**. Separate from public AM-Guru fork; source commit, exact pins, restoration, and single-side verification needed |

Original bundle/component hashes are preserved in the [research snapshot](../data/upstream-snapshot.json). When creating a device inventory later, record full/per-side hashes, read method and time, boot/main/case/hardware distinction, host-tool commit, and iOS build identifier. Reported strings, original distributed images, and actual device readback are not confused.

Subsequent local builds/tests, new hashes of original 2.4, and browser production-gate assessment are in [offline verification](../research/offline-compatibility-check.md). The initial snapshot's unbuilt state describes first investigation and does not replace current verified results.

Subsequent codec execution evidence: Faceclaw/38's version-comparison region is identical to stock 2.3, and in 18 fixture runs including stock 2.4 every mismatch led to the update path. Actual version query, DFU, and boot were not executed. Main-only combinations remain **unknown**, and choosing transfer components alone does not guarantee codec preservation. See [codec comparison and execution boundary](../hardware/sensors-input/codec-version-comparison.md).

## 2026-11-17 virtual boot verification matrix

[Exact combinations and rejection/repeat evidence by task](../bootloader/bootloader-compatibility-results.md) and a [machine-readable matrix](../data/bootloader-validation-matrix.json) were added. Even if exact boot/main bytes match, reject without task-specific evidence. Actual hardware, left/right boots, and case remain unknown. Existing physical-device assessments in this table are not upgraded.
