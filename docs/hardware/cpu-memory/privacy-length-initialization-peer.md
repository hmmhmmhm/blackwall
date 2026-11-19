# Natural M55 Integration of Privacy, Length, and Test-Random Responses

bw-0293. Connected seven responses from the [original function contract](privacy-length-initialization-contract.md) to an opt-in virtual SPI/HCI peer. No physical glasses or case were accessed.

## Results

| Original main | Profile | Cumulative commands/responses | Next request |
| --- | --- | --- | --- |
| Stock 2.4 | `test-max-251` | 21/21 | `01252000` |
| Stock 2.3 | `test-max-251` | 21/21 | `01252000` |
| Faceclaw | `test-max-251` | 21/21 | `01252000` |
| Stock 2.4 | `test-min-27` | 21/21 | `01252000` |
| Stock 2.4 | New profile disabled | 14/14 | Existing `012a2000` |

The four candidates above were natural Renode M55 executions starting from original reset. Original main was not patched and PC/return registers were not forced. Existing virtual hardware, SRAM initialization, and peripheral response assumptions continue to apply. This does not prove full ROM boot or identical actual chip behavior.

Each candidate recorded 48 CS frames, 96 IOM commands, and 19 application reply drains. The next request was identified by connecting R8=4, R9=0, actual SRAM content at R10, and the original ring record. It stopped strictly at the original write-ready GPIO check and was not transmitted. Stop PCs were stock 2.4 `0x501676`, older stock/Faceclaw `0x549fce`. Even though PC matched the earlier point, send/receive counts and actual queue contents show progression to the next stage.

In isolated function tests the transmit queue was empty after the fourth Rand, but natural main subsequently generated `2025`. This is why isolated callback results were not interpreted as completed integrated initialization. The specific task/callback producing this request remained a follow-up investigation.

## Model scope

Added nullable `privacyInitializationProfile` to `BlackwallEm9305EventPeer`. It defaults to disabled and can be selected only with an explicit existing controller-information profile.

- `test-max-251`: resolving-list size 4, TX/RX 251 bytes and 2,120 µs.
- `test-min-27`: resolving-list size 1, TX/RX 27 bytes and 328 µs.
- Both profiles return only four public fixed eight-byte Rand vectors. They are not cryptographic randomness or device keys.

Checks exact request bytes, lengths, response lengths, and CS commit. It does not return success to arbitrary requests; additional commands after all responses are consumed and reset rearming are blocked. Existing information-command counters/records are limited to four so new commands do not mix in. Do not use this test profile as actual BLE firmware in an installation package or as a secure random source.

## Verification

- A red test requiring an unimplemented constructor confirmed `privacyInitializationProfile` was unsupported.
- Passed 327 default-profile, 525 small-fragment/minimum-length, 240 new-profile-disabled, and 58 existing two-command scenario checks.
- The first green test's prior limit-14 assertion was fixed to account for the new limit 21. This failure was not a virtual-model initialization error or firmware failure.
- Passed five natural executions and five separate saved audits. Raw captures were not modified and CPU was not rerun for auditing.
- Disabled-control CPU, instruction count, registers, and existing events exactly matched the immediately preceding 14-command baseline.
- Saved SRAM/packet/ring analysis and reanalysis with 43 pinned Python dependencies produced byte-identical reports.
- Existing IOM/keyDB/OTA-marker model hashes were unchanged. The only changed peripheral was the HCI peer in the reset file.

A control description inherited from an existing plan referred to the information profile; its semantic description in the saved audit was corrected to the privacy profile. Capture and execution configuration were preserved.

Tools: `tools/prepare_privacy_length_candidate.py`, `tools/inspect_privacy_length_profiles.py`, `tools/run_native_candidate.py`. Private evidence is tracked by simulator `privacy-length-peer-verification-01/manifest.json`. The first stock 2.4 capture is `privacy-length-main-01`; others are `privacy-length-main-02/{stock23,cfw}`, `privacy-length-minimum-01/stock24`, and `privacy-length-control-01/stock24`.

## Next behavior and limits

`2025` is LE Read Local P-256 Public Key. It must not be handled as ordinary Command Complete alone; Command Status and a separate completion event need investigation. Checked the search index for the [distributed SIG specification §7.8.36](https://community.renesas.com/cfs-file/__key/communityserver-discussions-components-files/297/Core_5F00_v5.2.pdf) and [official completion event §7.7.65.8](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html). First analyze original consumption of public-key coordinates and test vectors, error paths, and subsequent persistent-storage intent.

The next goal is to connect this asynchronous initialization and app initialization notification and advance toward the natural app/display path. Actual pairing, key preservation, ACL traffic, normal app loop, and 576×288 display remain unverified. The web installer, recovery boot, and CFW installation artifacts were not modified here. Overall product completion remained scope v2, 13/29 = 44.8%.
