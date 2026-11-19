# HOSTCCISIDLE and OTP Read Readiness Contract

Task `bw-0202`. Investigated the original function following [CRYPTO power/NVM readiness](crypto-power-ready-model.md) and public upstream models. Peripheral models and the native execution endpoint were unchanged.

## Current original path

The current stop is an **OTP word-read wrapper readiness check**, not submission of a cryptographic-operation descriptor. The following instructions were confirmed in all three originals:

| Stage | Original behavior |
| --- | --- |
| Offset check | Requires four-byte alignment. Offset must be less than `0x3fd`, so the maximum aligned offset is `0x3fc`. |
| Power check | Confirms CRYPTO bit 21 and OTP bit 27 are both on in DEVPWRSTATUS. |
| HOST idle check | Checks whether bit 0 of `0x400c0a7c` is 1. If not ready, function result is 7. |
| OTP busy check | Loops until PTMSTAT bit 0 at `0x40014ac4` becomes 0. This short loop has no timeout or function call. |
| Word read | Reads one word from `0x400c2000 + offset` and stores it at the SRAM destination. |

SVD HOSTCCISIDLE includes engine, PKA, RNG, NVM, AHB, and other status fields besides bit 0. The current original check consumes only bit 0. The full reset word is `0x3b9`, but other fields are not inferred to be normal physical state. PTMSTAT BUSY is bit 0 and separate error/lock/failure fields also exist.

| Input | Readiness function | Read wrapper |
| --- | --- | --- |
| Stock 2.4 | `0x5606fa` | `0x560736` |
| Stock 2.3 / Faceclaw 38 | `0x52f7e6` | `0x52f822` |

The wrapper currently retains offset `0x340` and an SRAM destination. If the readiness check passes, the next requested address is `0x400c2340`. **That address had not yet been read and no contents were supplied.** Separate program-store and busy-wait code also follows the wrapper, so read support must not be expanded into permission to write the OTP window.

## Unknown OTP bank and data meaning

Correction (`bw-0204`): the earlier header's base definition was missed. [Bank/consumer reverification](otp-window-consumer-contract.md) compared base `400c2000` and absolute `2340` together and confirmed INFOC customer quadrant 2/3 mapping. The following is preserved as the investigation boundary before that correction. Physical contents remain unknown.

At that point the correspondence between the physical window and INFO0/INFO1/INFOC was not established. Numeric offset `0x340` in the public INFOC header is also used for a customer keybank item. A matching number alone does not establish that this window is that bank or, conversely, a serial-only region. Even if an upper caller checks a string, that alone does not establish storage-region meaning or actual data.

No physical key, factory calibration, serial, or device dump was read. Do not supply arbitrary 0/FF, definitions from another bank, or a fake key as the current word's normal value. If a synthetic factory fixture is needed later, distinguish it from actual device data and separately verify the original consumer's format, range, and error handling.

## Upstream model reuse investigation

Pinned the current recursive [Renode infrastructure](https://github.com/renode/renode-infrastructure/tree/5fd632c6c6e2f9e42699f55723fd3be2bde9b31e) tree at commit `5fd632c6c6e2f9e42699f55723fd3be2bde9b31e`. The API response had `truncated=false` and its SHA was preserved. The tree has no path containing CryptoCell. This alone does not prove the absence of every implementation body, alias, or external model.

Read actual source and LICENSE for MIT-licensed `AESServiceProvider` and `STM32H7_CRYPTO` and compared blobs/SHA with the tree. The former is an algorithm helper accepting an internal memory manager and bus; the latter is another device's register adapter. Neither was assessed as directly connectable to the current Apollo510 path. Since current execution is at an OTP read gate, building an AES engine now was not established as necessary to solve the next boundary. If actual algorithm requests are confirmed later, consider helper reuse while separately checking ABI/API compatibility between installed Renode 1.17 and current master source.

Also checked the HAL recursive tree pinned at commit `61b293a49db34030c545f99101f7ebf6a3050314`. Expected Apollo510 `hal/mcu/am_hal_otp.c/.h` paths returned 404; Apollo510 OTP-related register headers and docs were found in that tree. The INFOC header and OTP register HTML were pinned by blob/SHA. No OTP implementation from another chip was copied unchanged.

## Evidence and next implementation

The 46 checks in `tools/inspect_crypto_host_idle.py` compared current SVD/header pins, bit 0 of both registers, source inventory, MIT license, blobs/SHA, three pinned mains/existing native logs/reports/assets, power/idle checks, timeout-free busy loop, offset validation, actual window load, and separate program store. Results are outside Git at `simulator/crypto-host-idle-contract-01/report.json`; upstream originals/tree/hashes are in `crypto-init-research-01`. No new native execution occurred.

Next create an explicit mock profile for read readiness. Handle HOST bit 0 and OTP PTM busy independently while retaining default unknown and blocked writes. If testing the busy loop, stop by blocking access at an explicit observation budget instead of running forever; do not manufacture a success branch or timeout. Even after readiness passes, the actual OTP word remains a separate unknown boundary.

The subsequent [read readiness model](otp-read-readiness-model.md) executed eight original conditions including three normal and busy/unknown/default. Normal cases stopped at OTP-word read and PTM busy at the observation budget; no device data was supplied.

There was no hardware access, scan, connection, RAM payload, OTP/fuse/security/MRAM write, OTA, or flash. Full factory initialization, whole boot, integrated display, and physical installation/recovery remained incomplete; product completion stayed 13/29, 44.8%.
