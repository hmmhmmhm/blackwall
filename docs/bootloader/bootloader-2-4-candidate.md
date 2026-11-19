# Local 2.4 recovery bootloader candidate

Status: **research candidate, not installable, not physically verified**. Existing web installation catalog and 2.3 candidate were unchanged.

## Original and changes

A git archive of upstream g2-bootloader-patch commit `6198d70e18293caebf8314d2e40bd3b1d0a5ee16` was extracted into a separate private directory. Base stock boot is 2.4.0.24, 149773 bytes, SHA256 `ecb91896234392e2b98ec80b1ac3ebf4aa27726d3cbed10927edf0b44d83d665`.

`tools/prepare_boot_24_candidate.py` checks that hash and original instructions at three hooks, then changes only specified source strings. It fails if an exact string is absent or occurs more than once. Targets in a separate copy are platform binding, linker, RAM recover MRAM address, patch generator, and validator. Upstream original checkout and existing web checks remain.

- Manager/update/boot hooks: 0x42E666 / 0x42E3E4 / 0x42E450.
- Stock update-flag/handoff: 0x42E57D / 0x42DFE9 (Thumb included).
- UART pin table: 0x434220.
- Append link: 0x434910. A three-byte 0xFF gap after the original aligns actual placement and link address.
- RAM recovery MRAM entry: 0x42E84D. The previous 0x42E83D is not used.
- The copy's check was replaced to allow only exact 2.4 original SHA. Hash checking was not removed and arbitrary images are not accepted.

Case source and case 1.2.57 dependency were unchanged. `make patch build/recover.bin` was run first, then `make all` for host tests. Case input was extracted from a retained official 2.3.2.14 bundle and separated from the 2.4 boot test fixture. No actual case execution, USB, or BLE connection occurred. LLVM/LLD 21.1.8 and existing offline Python environment were used.

## Artifacts and checks

Stored at `~/Library/Application Support/Blackwall/recovery/private-boot-24-candidate-01/`. Source archive, diff, original, dedicated key, build/rebuild logs, manifest, and artifacts are retained together. Key and images/generated headers containing it remain outside Git.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| patched boot image | 159744 | 5ac1b02d337b57e0d25886a06296df2d5932af1f31168c416e64b50c5417a91d |
| OTA boot component | 159872 | b95254ec99b140e7b2cf41a66ed86ebd5375bb7f80a1d97faaf5fdbad4e04b96 |
| RAM recover payload | 264 | 9abc30c98bec432981d0c40ded3159085f273700e6c3b54716e37360df8cb8b2 |

Boot image rebuilt with the same key/input is byte-identical. RAM payload passed upstream Make's 0/0x1000 relocation comparison. MRAM call literal `0x0042E84D` was confirmed in objdump.

`tools/verify_boot_24_candidate.py` independently checked:

- Original prefix after reverting three hooks equals all 149773 stock bytes.
- Gap three bytes are 0xFF; append blob 6116 bytes equals actual build blob.
- Manager BL connects to 0x4354B8, two handoff BLs to 0x434B2C, corresponding to build symbols.
- End padding is 0xFF; image ends 0x437000 without intruding into main start 0x438000.
- Four corruption controls in prefix/gap/append/padding all rejected.

## Candidate code host tests

`tools/run_boot_24_tests.py` ran 118 upstream tests. Final: **118 passed, failures/errors/skips 0, blocked device-access attempts 0**. Actual new `patch.bin`, `recover.bin`, and exact 2.4 stock boot were used. Handoff/flag/pin addresses and fixture names remaining in tests were replaced only in memory; original test files were preserved. Only macOS host crypto tests used Apple clang/system runtime.

First run passed 117 with one metadata-check error. `artifacts.py` recorded authentication-key hash only at an old link base, so the field was missing at the new address. The candidate preparation procedure and corresponding private-source condition were changed to 0x434910 and the full suite rerun. Failure/final logs and JSON and diff all remain private. The change is limited to metadata generation code.

Tests cover authentication, packet/CRC/boundaries, boot selection, streaming, recovery payload and stock MRAM wrapper, watchdog, and failure retry limits. BLE/serial access entry points were blocked; communication tests are mocks. Emulation passes with ROM writing and peripheral behavior substituted are not interpreted as physical write/recovery success. Recording the key hash under the new address condition does not disclose the authentication secret itself.

## Remaining verification

Structure, build reproducibility, and limited host behavior were checked. This does not establish complete scheduler/watchdog behavior, actual chip/ROM revision, power interruption, physical recovery, or integration with Faceclaw main. Limitations of existing RAM/ABI analysis remain in [direct analysis](bootloader-2-4-analysis.md). Version-specific recovery-payload selection and Faceclaw integration require additional checks.

The web installation gate is not opened merely because candidate files exist. The overall goal remains incomplete.

Follow-up [main handoff checks](combined-handoff-verification.md) passed 16 emulation conditions through reset entry for Faceclaw/38 and stock 2.4. Actual main startup and peripheral compatibility remain unverified.
