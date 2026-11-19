# Synthetic INFOC String Slots

Task `bw-0205`. Implemented a read-only synthetic fixture supplying only 128 bytes according to the [INFOC consumer contract](otp-window-consumer-contract.md). No actual OTP words, device backups, or keys were used. Three original mains read 32 words, output the last valid synthetic candidate, and stopped at an unsupported CRYPTO-off request during cleanup.

## Model boundary

`BlackwallOtpSerialSlots` covers `0x400c2340..0x400c23c0`, end exclusive, with aligned 32-bit reads only. By default the component is unattached and the existing word read remains blocked. Other INFOC addresses, writes, byte-width and unaligned accesses, and direct API inputs outside the range are rejected.

For attachment to root, the fixture's readiness owner must be the same object as root `OtpReadReadiness`. Reads require OTP/CRYPTO on, HOST idle=1, PTM busy=0, and prior observation of both readiness registers. Following [power-generation strengthening](otp-readiness-power-generations.md), only observations in the current power generation are valid. Data is created only by the constructor; external files/device input are not accepted. Reset clears counters/last address but preserves profile bytes.

| Profile | Contents |
| --- | --- |
| empty | 128 FF bytes; a synthetic format-rejection fixture, not actual OTP erased-bit state |
| mock-first | slot 0=`S211MOCK000001`, rest FF |
| mock-last | slot 0 as above and slot 7=`P100MOCK000002`, rest FF |
| invalid-prefix | slot 0=`X211MOCK000001` |
| invalid-digit | slot 0=`S211MOCK00000X` |

A slot with a string has 14 ASCII bytes followed by two NUL bytes. This does not indicate a manufacturer-reserved nonoperational serial namespace. Do not use it as evidence of actual identity, model, or official app/firmware compatibility. The profile is simulator-only synthetic input, not cryptographic keys or reproduction of all INFOC.

CLI `--otp-serial-profile` defaults to `none`. Selection requires explicit HOST idle, PTM clear, NVM idle, and existing active CRYPTO/OTP and blank NVdb/RX scenarios. There is no function to connect to an actual device or write OTP.

## Original execution results

| Condition | Word reads | Observed candidate state | Next block |
| --- | ---: | --- | --- |
| Stock 2.4 / mock-last | 32 | output=`P100MOCK000002`, r7=7 | CRYPTO off |
| Stock 2.3 / mock-last | 32 | Same | Same |
| Faceclaw 38 / mock-last | 32 | Same | Same |
| Stock 2.4 / mock-first | 32 | output=`S211MOCK000001`, r7=0 | Same |
| Stock 2.4 / empty | 32 | output unchanged, r7=FFFFFFFF | Same |
| Stock 2.4 / invalid-prefix | 32 | Same | Same |
| Stock 2.4 / invalid-digit | 32 | Same | Same |
| Stock 2.4 / default none | 0 | Scan incomplete | Existing OTP word read |

Compared the selected data's first 14 bytes and NUL in **SRAM output written by the original** using read-only snapshots at scan entry/end. Observed original behavior overwriting with the last valid candidate; the host did not inject output or r7. Rejection profiles retained the same first 15 buffer bytes as at entry. r7 is a diagnostic register state during cleanup, not a high-level function success/failure return code.

For every selected profile, readiness helper and word wrapper each returned 0 32 times; last read was `0x400c23bc`. The next request, `0x40021004=0x08000400`, attempts to clear the CRYPTO bit. It was blocked because on-domain off was unsupported at that point. PCs were stock 2.4 `494f3e`, stock 2.3/Faceclaw `489056`. Cleanup, full string-consumer return, and successful factory initialization were not yet verified.

All mains match pinned original bytes and ran from main reset. PC/branches, returns, and delays were not forced. Existing synthetic identity/memory/power and logical SDR assumptions remain. This is not full ROM/bootloader boot or physical OTP verification.

## Observation and verification

Selected profiles had 2,665 observations, default none 2,600, capacity 4,096 and zero drops. New scan entry/end and existing ready/word return labels were listed explicitly in the report's projection. Removing these labels and renumbering sequence in actual/previous observations confirmed preservation of prior selected events. NOR array/program/erase history also remained for all conditions. Compact observations are not a full instruction trace.

There were 368 unit/regression conditions: 55 each for five profiles, default none 6, foreign readiness identity 1, direct slot rejection for HOST busy/unknown and PTM busy/unknown 26, and existing readiness 30/CRYPTO 30 regressions. Checked range/alignment/little-endian, writes/widths, readiness not observed, power loss, data preservation after Reset, and malformed profiles/dependencies. Distinguish local-ready-mock unit tests from the eight original conditions above. Three CLI prerequisite errors were also rejected before output creation.

Outside Git under `simulator/`:

- `otp-serial-slots-unit-02`, `empty-unit-01`, `last-unit-01`, `prefix-unit-01`, `digit-unit-01`, `default-unit-01`, `foreign-unit-01`, `host-busy-unit-01`, `host-unknown-unit-01`, `ptm-busy-unit-01`, `ptm-unknown-unit-01`, `readiness-regression-01`, `crypto-regression-01`.
- `otp-serial-slots-main-01/`: inputs, hashes, logs, and reports for the eight original conditions above.
- `otp-serial-slots-cli-01/report.json`: three CLI rejections.
- `otp-serial-slots-verification-01/report.json`: 257 final checks comparing current compiled model, unit/native logs and reports, original/derived hashes, source observation points, projection, 32 successful reads, actual output bytes, r7, cleanup guard, default boundary, and history preservation.

Red was the absent new component. After the first 52 conditions passed, adding a 64-bit end address to the direct API reproduced an array-index exception from `address+4` overflow. Changed the comparison to `address > end-4` and passed a regression rejecting out-of-range/overflow inputs without side effects. Initial results and failure logs were preserved. As in the prior stage, the foreign-readiness negative test is classified as an expected platform exit 133 confirming the exact constructor exception and no CPU start; it is not counted as a normal execution success.

An agent inheriting the parent model reported no Important/Critical defects in read-only review. Its suggested direct slot-rejection tests for four readiness states were added. Astra was not used.

## Remaining limits and next steps

Readiness observation counters were lifetime history. If an individual power owner were reset only by the host and then reactivated, old history could remain. Current guest off was unsupported and root Reset also initialized readiness and slots. Before adding actual off/on support, an epoch/observation-history policy needed to be defined. Do not interpret this as physical power-cycle verification.

Next investigate CRYPTO/OTP power-off prerequisites, idle/clock state, and PTM busy handling in original cleanup. Do not change the current guard into success or force cleanup return. Only afterwards can the full string-consumer return and upper factory initialization be verified.

There was no glasses scan/connection, RAM payload, OTP/fuse/security/MRAM write, OTA, or flash. Whole boot, integrated display, and physical installation/recovery remained incomplete; product completion stayed 13/29, 44.8%.
