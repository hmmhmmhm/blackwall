# Device information inspection boundaries without installation

2026-11-10. These are source inspection results; no connection or command was made to actual glasses or case.

## Methods and side effects

| Path | Information obtainable | Behavior confirmed in source | Current assessment |
| --- | --- | --- | --- |
| Provided official app photos | Combined main 2.4.0.24, model S211, app 2.4.0 | Read material already provided | Confirmed. Does not establish boot, hardware revision, or independent left/right state |
| Standard BLE Device Information Service | Model, hardware revision, and firmware revision strings, only when supported | Webflasher's `readG2DeviceInformation` uses characteristic `readValue()` after accessing the service | Candidate without application writes. Connection and OS security processes are not guaranteed stateless. Not executed |
| Faceclaw `DeviceInfoProbeFlow` | Left/right main versions and firmware extension strings | Connects and authenticates both sides, retries pairing/bond, sends prelude and settings query | Not a simple passive read. A new bond may be saved, so excluded from current automatic execution |
| Case `restore_application` | Version in case startup banner | Sets DTR/RTS and receives banner after reset | Despite its name, not a firmware file restoration function; it restarts the case and is not classified as a passive query |
| Case `open_rom_loader` | Entry for ROM commands and chip identification | Selects system memory via DTR, resets with RTS, sends SYNC | Changes case execution mode. Not executed in this investigation |
| Patched boot RAM dump/recovery | Memory access provided by an installed patch | Requires boot interception, case relay, and RAM code execution | Not treated as a way to identify stock boot without installation |

There is no evidence that the standard BLE firmware revision string equals the bootloader hash. No response is not conclusive evidence of failure or incompatibility. The serial-number characteristic may be blocked by browser policy; do not bypass this or store device identifiers in documentation.

## Boundaries for next verification

Current photos alone cannot clear the installation gate. Even if a BLE read is selected later, isolate a standard service query on one side; if authentication, pairing, or absence of the information service occurs, do not arbitrarily switch to Faceclaw authentication or case tools. Before actual execution, confirm the connection and possible bond-storage scope with the user. This document is not authorization to execute.

Original boot hash, hardware revision, case version, and mixed firmware combinations remain unconfirmed. In particular, avoid circular reasoning that uses a dump available only after installing a recovery patch as evidence of pre-installation compatibility. If no other supported nondestructive identification evidence exists, leave the item unconfirmed.

## Pinned source evidence

- [Webflasher information read](https://github.com/AM-Guru/EvenRealities-WebFlasher/blob/2fcdb888facfe9c56672cbe2a3da741b44033c44/src/lib/g2BleOta.js): `readG2DeviceInformation`.
- [Faceclaw probe](https://github.com/jimrandomh/faceclaw/blob/70ec2a0d6afd92e8185234e57ab013fcb596bf4d/native/kotlin/shared/src/commonMain/kotlin/com/faceclaw/app/g2protocol/DeviceInfoProbeFlow.kt): `bringUpArm`, `queryArm`; `sendPrelude`, `readSettings`, and `authenticate` in `StockLinkSession.kt` in the same directory.
- [Case ROM tool](https://github.com/drdaeman/g2-bootloader-patch/blob/6198d70e18293caebf8314d2e40bd3b1d0a5ee16/tools/g2patch/case_rom.py): `open_rom_loader`, `restore_application`.

Distinguish behavior implemented in source from the author's comments about physical observations. There are no measurements from the Blackwall user's device.
