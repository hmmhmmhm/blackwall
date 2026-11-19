# Original address setting and advertising initialization contract

bw-0298. Original ARM functions were investigated from the state immediately before `2005` transmission in the preceding natural M55 run. No new natural M55 run or physical device connection was made.

## Address source and constructor

The six-byte addresses of all three inputs matched the public BDA previously set by `fc43` in the current virtual profile. The two most significant bits were 3 and the remaining 46 bits were neither all 0 nor all 1, matching static-random format. Actual device provenance, uniqueness, random generation, and entropy were not verified.

The original `2005` constructor copies six input address bytes. Native address, ascending, and descending inputs were tested for each image, confirming byte order in the completed internal HCI packet is preserved. This is not evidence of address validation. The initial test assumption that the constructor immediately outputs to the transport queue was incorrect, so packet composition was checked after original copying and before enqueue. Branches and command-ready values were not forced.

## Five transactions confirmed

| Request | HCI parameter length | Observed value |
| --- | --- | --- |
| `2005` LE Set Random Address | 6 | Same as virtual public BDA |
| `2006` LE Set Advertising Parameters | 15 | Interval min/max 160, type 0, own-address type 1, channel mask 7, filter 0 |
| `2008` LE Set Advertising Data | 32 | 28 valid bytes, AD types 1/255 |
| `2009` LE Set Scan Response Data | 32 | 21 valid bytes, AD type 9 |
| `200a` LE Set Advertising Enable | 1 | Enable 1 |

Address-setting format was compared with a [distributed copy of SIG specification §7.8.4](https://community.renesas.com/cfs-file/__key/communityserver-discussions-components-files/297/Core_5F00_v5.2.pdf). Each original write request was returned an assumed seven-byte Command Complete with exact opcode and status 0. AD length structure was also checked. Address, name, manufacturer payload, and original bytes are retained only as private assets.

After the fifth response, all three images reached UART1 FR read `0x4003a018`: PC stock 2.4 `0x5ae038`, stock 2.3/Faceclaw `0x5ad92c`. The standalone function runner lacks UART1, so execution stopped there without arbitrarily filling a value. This path requests advertising enable and consumes its completion response; it is not evidence of actual radio advertising or complete app/boot.

## Response acceptance and command-ready controls

Opcode 0 must not be interpreted as an invalid-opcode control. [SIG §7.7.14](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html) defines it as a command-credit update event not associated with a particular command. Final tests used six-byte `04 0e 03 01 00 00` with no return parameters.

| Virtual response to first address request | Subsequent original request |
| --- | --- |
| No event | None |
| Status 1 | `2006` |
| Opcode 0, credit 1 | `2006` |
| Unsupported opcode `7ffe`, credit 1 | `2006` |
| Normal opcode, credit 0 | `2006` |
| Add opcode 0/credit 1 after credit 0 response | Two transport records including `2006` |
| Wire one byte short of declared length | None |

The ready helper reached from the original Command Complete consumer was identified. With inputs 0/1/7/255, it stored 1 in the ready byte before starting queue processing in every case. ARM code storing the constant matched synthetic calls of the original helper. Field offsets differed: `+0x22` in stock 2.4 and `+0x1a` in older versions/Faceclaw. Ready byte addresses are `0x20075f86` and `0x20076ba2` respectively.

These results are limited to this original implementation, state, and synthetic inputs. Generating the next request alone does not prove validation of prior opcode/status or safe error fallback. Nor is it evidence that actual EM9305 sends credit 0 or these unsupported responses. The planned peer explicitly supplies only correct responses and does not assume original firmware safely filters arbitrary responses.

## Execution scope and reproduction

Original Apollo ARM binaries ran in Unicorn M7 with synthetic entry, stack, registers, and hash-verified full native SRAM. Original HCI ring pop → parser → upper handler and necessary original WSF queue/handler/free were used. Constructor was observed at copy-complete boundary and ready helper at store-complete boundary. All are distinct from natural M55 task scheduling.

- Three images × eight conditions, 24 scenarios. Five normal initialization stages and response controls were checked.
- Nine address-constructor inputs and 12 ready-helper inputs. Distinguished 150 original-function returns, 21 explicit instruction-fragment boundaries, and three UART1 stops.
- Initial offset assumption was rejected because older ready fields differ from 2.4. Each original's consumer, literal, and store were checked and incorporated in the final tool. Exploration failures were retained.
- Final private `address-advertising-source-05` and `address-advertising-source-06`, analyzed with 51 frozen dependencies, matched byte for byte across 26 files including reports and saved SRAM.
- Four peripheral models have the same hashes as the previous stage. There was no native main rerun, physical access, web installer, recovery boot, or installation CFW change.

Tool: `tools/inspect_address_advertising.py`. Evidence is traced in private simulator `address-advertising-verification-01/manifest.json`. `advertising-fixtures.json` retains five exact requests/responses and provenance hashes per image; `advertising-summary.json` retains data-length and parameter summaries.

Next connect five transactions as an optional peer and observe advertising initialization and later app/display paths in natural M55. Since execution may continue waiting for a connection after enable, first confirm explicit observation termination and SRAM collection contracts. The current runner's full SRAM exporter requires guest stop. Do not substitute idle observation for normal boot or product completion. Overall product completion is scope v2, 13/29=44.8%; integrated display and physical installation readiness remain incomplete.
