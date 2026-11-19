# Review of Existing Restore Paths Independent of Boot

2026-11-17 · bw-0568. Progress remains **7/12 = 58.3%**. Alternatives after self-overwrite of the existing boot-resident writer were investigated using actual source, image validators, and stock ARM. No new firmware payload, physical connection, or OTA installation was executed.

## Existing paths identified

The current remote HEAD and retained full clone are both commit `42e27e9c999a340e8b7af406b83a52dc56fcf926`. The license is MIT. [tools/flash.py](https://github.com/drdaeman/g2-bootloader-patch/blob/42e27e9c999a340e8b7af406b83a52dc56fcf926/tools/flash.py) transmits only `ota/s200_bootloader.bin` using the stock app's BLE OTA. This is not a path using the boot RAM API receive callback. It requires a working main app, so this path alone cannot recover a dead main.

However, `--verify-port` runs a checksum payload through the newly patched boot and checks CRC twice. Thus **independence of the transport path and independence of post-installation readback verification are different**. After restoring stock boot, patched UART HELLO cannot be assumed to remain available. A BLE END response or stock authentication liveness is not equivalent to readback of all boot bytes.

`recover.c` and `ramload.c` use `api->recv` and `api->send` every 256 bytes. The existing `ramload` that loads an image into ITCM is not itself a complete stock-restore tool independent of UART/recovery APIs. Upstream examples list echo/checksum/dump/recover/ramload; no complete standalone boot-restore payload was found in that list. Failure to find one is not proof of impossibility.

## Actual image gate and write length

The actual `component()` in firmware.py was invoked offline. No transport/Bleak/serial modules were imported. For 2.3, the stock 149760 bytes were extracted after CRC checks from official bundle SHA 26b60676…; for 2.4, the pinned stock image is 149773 bytes, SHA ecb91896… .

| Tool / input | Actually accepted | Generated payload | Bytes not covered through patch end 437000 |
| --- | --- | ---: | ---: |
| Current 2.3 / original raw | Yes | 151552 bytes, 37 pages | 8192 bytes |
| Current 2.3 / original + FF to 159744 | Yes | 159744 bytes, 39 pages | 0 |
| Current 2.3 / original + 0 to 159744 | No | None | — |
| Legacy 2.4 research port / original raw | Yes | 151552 bytes, 37 pages | 8192 bytes |
| Legacy 2.4 research port / original + FF to 159744 | Yes | 159744 bytes, 39 pages | 0 |
| Legacy 2.4 research port / original + 0 to 159744 | Yes | 159744 bytes, 39 pages | 0 |

Different versions, truncated originals, and one-byte prefix mutations were also rejected by each tool. Actual outcomes and source SHA were recorded for 12 inputs.

Current upstream checks the stock prefix or allowed complete patched SHA and remaining FF padding. In contrast, **the existing 2.4 research port has weaker validation**. It checks the SHA after reversing reviewed hooks in the original stock prefix and checks hook ranges, but does not check the entire tail hash/FF condition, allowing arbitrary tails. Do not treat this as the same security strength or installation safety as current upstream. No gate was weakened or bypassed in this investigation. The 2.4 port remains a non-installable research asset.

Supplying only original raw data yields page padding through 435000, potentially leaving the final 8192 bytes of the existing patch. However, execution has not yet established whether actual OTA always writes exactly the payload length or erases additional space. The table shows **actually generated component geometry**, not successful verification of the OTA persistent footprint. Do not assume an actual device tail is 0 or FF.

## Candidate path in stock 2.4 main

Filename and MRAM-key literal candidates were located in original main SHA df8cfddf… and instructions interpreted. A previous native boot's actual SRAM snapshot was also compared with a pinned SHA.

- Branch 446a1c..446a30, with state+2c = 3 and state+28 = 1, sets destination 410000. The complete path by which a received header forms this state remains unverified.
- MRAM operation table 20000394 in the earlier native SRAM contained read 5c69d1 / write 5c69f9 / erase 5c6a21 and a 4096-byte unit. These fields alone do not show completion of a full OTA session.
- The candidate write-callback chain is **5c69f8 → 488d34 → 4f5864 → 4f5810 → 5791e8**. These main instructions are above 438000. 5791e8 reads and calls program entry 0200ff21 from main's immutable table at 7807d4. The chain does not directly depend on a boot UART callback. Not all dependencies inside ROM have been analyzed.
- 446ab4 is a readback/compare candidate, and 480dc8 contains byte/word comparison code. The first file's name `copier-candidate` means an analysis candidate, not an established name for a complete installer.

There is also a concern: 488d34 does not pass 4f5864's return status unchanged to the upper callback, and 5c69f8 returns 0 once the range check passes. Therefore **callback 0 or transport ACK alone must not be treated as successful ROM writing**. Actual MRAM readback and failure handling in the original verification path must also be checked. This is a current source-supported observation, not the result of a new main ARM call or OTA transmission in this task.

## Evidence level and next experiment

| Category | Evidence in this task |
| --- | --- |
| Physical validation | None |
| Code/actual tool results | Pinned upstream source, 12 actual component-gate calls, stock ARM interpretation, immutable ROM table, and prior native SRAM |
| Developer claims | README's 1 KiB MRAM hardware test, full application replacement untested, and description of stock OTA copy timing. Do not carry these over as our physical validation |
| Design hypothesis | Two-stage path: restore main through boot RAM API, then restore boot through working stock main OTA |
| Unknown | Complete original main OTA input → write/readback execution, actual ROM permissions, case/sides, original tail, full-stock and failure-recovery certification |

The next verification unit is actual M55 execution in 4 KiB units against the original main MRAM write callback/adapter, checking ROM errors and readback mismatches. Label a diagnostic function invocation as such; do not substitute it for natural BLE OTA or completed full-stock restoration. Later connect the same path to actual virtual ATT/OTA inputs. Do not skip original checks or copy functions with arbitrary PC/success returns and claim full OTA success.

BV02/05/06, blocked by original ROM/factory INFO1, remain unchanged. [PROTOCOL.md](https://github.com/drdaeman/g2-bootloader-patch/blob/42e27e9c999a340e8b7af406b83a52dc56fcf926/PROTOCOL.md) describes boot 2.3.2.14/main 2.4.0.24/hardware 5/case 1.2.57 as a supported combination. Record this as an upstream documentation claim; do not confuse it with main 2.3.2.14 from the same bundle compared in an earlier native run. The user's 2.4 app/firmware screens alone do not establish boot version or hardware 5. This mixed combination is also a candidate for the future virtual version matrix.

## Preservation and reproduction

Private `simulator/upstream-independent-restore-bw568-01` retains gate-probe.py, gate-report.json, literal candidates/instruction interpretations, main-mram-abi-map.json, and source-manifest.json. Proprietary images and SRAM were only read from existing private originals; they were not copied or committed to Git. No new native job, build, or connection occurred, and duplicate build/dump data to clean up was zero bytes. Small analysis text/JSON/source files are retained as key evidence.

```sh
bw_assets="$HOME/Library/Application Support/Blackwall"
"$bw_assets/recovery/private-boot-candidate-01/host-venv/bin/python" -B "$bw_assets/simulator/upstream-independent-restore-bw568-01/gate-probe.py"
```

This command calls only the actual image gate/component construction, not firmware installation CLI or transport. It can rewrite existing results; to avoid overwriting retained results, copy the probe to a new private folder before running it.
