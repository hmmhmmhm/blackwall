# even-g2-protocol Reference Review

Conclusion: **This is a directly relevant reference for investigating G2 BLE and reuse of stock text features. It should not be adopted as a verified general-purpose transport or schema.** Unlike the G1 decompilation material on low-level panel SPI/MSPI, this repository addresses communication between a phone and G2 app services.

## Pinned source and inspection scope

[i-soxi/even-g2-protocol](https://github.com/i-soxi/even-g2-protocol) was pinned at commit `b227335f5fbecb7d4ede3748c36e098ef88850fa`. Eleven files including the README, documentation, examples, and proto, plus one public teleprompter capture, were retained outside Git. Each file's SHA-256 and Git blob were checked against the tree. Results are in private `simulator/even-g2-protocol-research-01/sources.json`.

`tools/inspect_even_g2_protocol.py` performed 34 offline audit checks, including reproduction of the failures below. “34 checks passed” does not mean the upstream schema or actual communication works. Results are in `simulator/even-g2-protocol-verification-01/report.json`; protobuf compilation errors are in `protoc.log` in the same directory.

The examples were not imported or executed in full. Only 11 inspected synchronous pure helpers were selected from the AST for encoding tests, with a fixed mock time. Bleak import, scanning, connection, notify registration, GATT writes, and firmware installation were not performed.

## Useful information and application

| Source | Confirmed source content | Blackwall use |
| --- | --- | --- |
| `docs/ble-uuids.md` | Author's mappings including 5401 write, 5402 notify, and the 6402 display channel | Candidates for future G2 BLE adapter discovery and classification. Do not hard-code fixed ATT handles or MTU 512 as a universal device contract |
| `docs/packet-structure.md` and examples | Eight-byte header, payload CRC16, sequence, and service bytes | Comparison material for an offline packet codec. CRC matched independent `binascii.crc_hqx(...,FFFF)` results for three vectors |
| `docs/services.md` | Candidate services including auth, device-info, teleprompter, dashboard, and config | Search list for stock service dispatch. Recheck names, read/write operations, and response meanings in the original 2.4 firmware |
| `docs/teleprompter.md` and examples | Candidates for seven session packets, display settings, pages, markers, and sync | Future mock scenarios for stock text features; do not claim success on stock 2.4.0.24 |
| `proto/g2_protocol.proto` | Its own comments describe a field structure inferred from captures | Clue for locating original G2 protobuf handlers; do not use as schema generation input |

The examples show a BLE path for an external program to write directly to G2, not an API for reading internal official-app data. They do not establish concurrent connections or session coexistence with the official app, access to notification contents or the app database, or reuse of all data. The examples also lack a 6402 raw-rendering packet encoder; do not treat them as a contract for arbitrary shapes, animation screens, or 576×288/640×480 framebuffers.

## Reproduced limitations

1. **Schema compilation failure.** `TimeSyncData` assigns field 2 to both `unknown1` and `transaction_id`. Local protoc exited with this error. The upstream file was not modified.
2. **Time synchronization tag mismatch.** Interpreting bytes `82 08` as a varint tag yields field 128/wire type 2. The proto declares sync as field 16. Compare both against the original firmware and capture before deciding which matches the G2.
3. **Length limit without fragmentation.** `build_packet()` stores body length + 2 in one byte, limiting payload to 253 bytes; length 254 fails. A 25-character × 10-line ASCII page and a Korean page of the same dimensions also produced `ValueError` when passed through `format_text()` → `build_content_page()`. Documentation about MTU 512 and multiple packets alone does not establish fragmentation in this example.
4. **Responses are not evaluated.** The notify callback ignores received content and sends the next command after a fixed sleep. CRC and length consistency were checked for seven auth packets, but successful or failed session authentication handling was not validated.
5. **Target-selection fallback.** If the requested side name is not found, the code selects the first G2 discovered. This default is unsuitable for Blackwall's per-side identification and approval rules. It does not mean a transmission occurred.
6. **Capture validation incomplete.** The supplied `teleprompter-session.log` is a binary with btsnoop magic and version 1, not a text log. Header linktype 768 was observed and was not decoded in this inspection. It was not arbitrarily corrected or used as evidence of valid wire CRC or handshake. The public file's contents and device identifiers were not printed or committed to Git. Three other captures have not yet been inspected.
7. **Device/firmware combination unknown.** Do not equate the author's Working table with compatibility of our device on 2.4.0.24. Observations in the new repository are not measurements of our device.
8. **Code redistribution basis unknown.** No root LICENSE/COPYING/NOTICE was found in the pinned tree. For now, use it as a source and analysis lead in isolated offline comparisons; do not copy it into product code.

## Next application sequence

### Current reference recheck — 2026-11-12

At the user's request, `git ls-remote ... HEAD` was checked again. HEAD matched the pinned commit `b227335f5fbecb7d4ede3748c36e098ef88850fa`. The existing 34-check audit report was reread: `passed=true`, while BLE import, hardware access, and 2.4.0.24 compatibility verification were all false. The same source analysis and tests were not repeated.

Do not use this repository as direct implementation evidence for NOR/MSPI or chip peripheral models needed by the current Renode boot path. Once original ARM code reaches a BLE service-handling boundary, use it to compare packet inputs and handlers. The stock text-display path is a candidate for an initial display experiment, but do not extend that claim to arbitrary shapes, animation, or access to internal official-app data.

When full main firmware reaches the BLE service-handling boundary, compare UUID, service, and field candidates with the original handlers. Use this repository for that investigation and mock-packet scenarios. Do not hard-code opcode meanings or successful authentication in place of actual firmware behavior. Physical device experiments are outside this request and retain their separate approval boundary.

This review did not change the overall completion criteria. Integrated BLE (S5), full boot (S6), and integrated display (D3) remained incomplete; overall product progress was 13/29, 44.8%.
