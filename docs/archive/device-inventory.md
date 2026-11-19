# User device information

Observed 2026-11-10. Evidence: two user-provided photos of the official app's glasses information screen and the App Store screen. No device connection, direct query, or image readback was performed. The device serial number and MAC address in the photos, and the original photos, are not included in Git documentation.

| Item | Observation | Scope of evidence |
| --- | --- | --- |
| Device name | Even G2 | Official app glasses information screen |
| Model name | Even G2 B-Grey1 | Official app display |
| Model number | S211 | Product model number, not equated with boot patch hardware revision 5 |
| Glasses firmware | **2.4.0.24** | Combined official app display, not a direct query of each temple |
| Official app release version | **2.4.0** | App Store “What's New” version, distinct from checking the installed app's internal version/build |
| Installed official app version | **2.4.0** | User confirmed it matches the App Store display; separate build number unconfirmed |
| Left main version | Independently unconfirmed | Combined firmware display is not automatically copied |
| Right main version | Independently unconfirmed | Same |
| Both bootloader versions/hashes | Unconfirmed | Main version 2.4.0.24 does not establish boot 2.3.2.14 |
| Hardware revision | Unconfirmed | S211 is a separate model identifier |
| Case firmware | Unconfirmed | User confirmed the official app does not display the version; do not repeatedly ask them to find it there |
| Full stock/custom state | Unconfirmed | The official app's version display is not evidence that firmware is unmodified or entirely stock |

## Effect on current assessment

2.4.0.24 matches the main version in the boot patch documentation reviewed. Boot, case, and hardware conditions are separate, however, so this does not change the installation compatibility assessment. Using current g2flash's 2.3.0.24-based CFW as-is would require review of the version downgrade and boot/resource combination. User photos alone do not establish the safety of downgrade, boot patching, or web installation.

Additional file inspection: the official 2.4.0.24 bundle's boot payload SHA is `ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665`, different from the SHA supported by the current boot patch, and the patcher rejected it. The user's actual device boot was not read. See [offline verification](../research/offline-compatibility-check.md).

The user confirmed the installed app version and whether the case version is displayed. Discuss the actual case version and methods to identify each side and query boot/hardware after classifying side effects in source. Do not insert reset, unpairing, or update into information gathering. Providing photos and version information is not authorization for hardware work.

Source classification of query paths is recorded in [device information inspection without installation](device-inspection-boundaries.md). It distinguishes a standard BLE read candidate from tools involving authentication, bond storage, or case reset; no actual connection was made.
