# INFOC Window and G2 String-Slot Consumer

Task `bw-0204`. Statically analyzed bank mapping and the actual consumer for `0x400c2340` following the [OTP read readiness model](otp-read-readiness-model.md). Models, OTP backing, and the main execution endpoint were unchanged.

## Correction to earlier bank analysis

An earlier investigation missed the base definition in the preserved public header and recorded the window's bank as unknown. Pinned `am_mcu_apollo510_otpinfoc.h` contains both `AM_REG_OTP_INFOC_BASEADDR=0x400c2000` and customer quadrant 2 KEY0 absolute address `0x400c2340`. These exactly match the address calculated by the original, so the conclusion is corrected to a **source-supported INFOC mapping**.

The 32 words beginning there correspond to customer keybank quadrants 2 and 3. Distinguish the manufacturer's region name from how G2 uses data. The name alone does not establish that cryptographic keys are stored on this device, nor does it justify generalizing that only serials are present. No physical OTP bytes, security state, or actual contents were read.

The source is the [pinned INFOC header](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/regs/am_mcu_apollo510_otpinfoc.h). Rechecked existing manifest SHA-256 and Git blob and connected base and 32 offsets/absolute addresses to executable checks. Check both base and absolute address rather than inferring a bank from a numeric offset alone.

## What the original consumer requires

| Input | Consumer entry | Word-read call |
| --- | --- | --- |
| Stock 2.4 | `0x4d1a80` | `0x4d1bdc` |
| Stock 2.3 / Faceclaw 38 | `0x4c40d0` | `0x4c422c` |

The same structure was confirmed in all three originals:

1. Check eight slots starting at offset `0x340`, with a 16-byte stride. Each consists of four word reads. Range is `0x400c2340..0x400c23c0`, end exclusive, totaling 128 bytes.
2. After reading 16 bytes, inspect/copy only the first 14 and NUL-terminate local/output index 14. The final two input bytes are not used for string checks.
3. Compare the first two bytes with `S2` or `P1`. Each byte at indices 8..13 must be accepted by the original digit helper, which returns 1 for ASCII `0`..`9`.
4. No separate character-class check for indices 2..7 was found in this function. Do not extend this rule into the manufacturer's complete serial grammar or printable/UTF-8 validation.
5. On a valid candidate, update 14 output bytes and selected index, then continue scanning. If all reads complete normally, the last valid slot remains.
6. A word-read error stops the scan and goes to cleanup. If there was already a valid candidate, the selected index/output are preserved. Do not conclude that a read error always fails the entire result.

Cleanup calls CRYPTO and OTP power disable, then returns a result according to the selected index. Current main had stopped at the first word read, not executed through cleanup. Successful return of the full consumer and compatibility with physical factory data remain unverified.

## Evidence and isolated execution

The 89 checks in `tools/inspect_otp_serial_consumer.py` compared header pin/base/32 words, three originals/existing native reports/asset hashes, slot loop, copy/terminator, prefix/digit branches, last-match updates, and read-error cleanup.

In Unicorn, **only helper bytes from pinned originals** were placed in a separate address space and executed with standard function entry and synthetic LR return. PC was not changed mid-execution and function results were not overwritten; reaching the return point and an instruction-count limit were checked.

- Digit helper: 256 byte inputs per original, 768 calls total. Only ASCII digits returned 1.
- Prefix helper: for each original, individually varied each of the two positions in `S2` and `P1` over 256 byte values, totaling 3,072 calls. Match was checked at comparison length 2. This did not exhaust all 65,536 two-byte combinations.

This was not main-reset execution, execution of the entire consumer, or actual OTP emulation. Nor was it merely checking a reimplemented high-level parser. Remaining consumer control flow was verified statically only. No actual OTP words were supplied.

Final results are outside Git in `simulator/otp-window-consumer-contract-02/report.json`. The initial 74 checks/digit 768 calls remain in `contract-01`. A read-only review by an agent inheriting the parent model reported no material format/branch interpretation errors. It suggested explicitly stating prefix mutation coverage and synthetic-value meaning, which was incorporated. Astra was not used.

## Proposed next mock fixture

The next implementation candidate is a **simulator-only synthetic string slot** permitting reads only of the 128 bytes above. It is not claimed to be an identifier reserved by the manufacturer namespace. It does not replicate all INFOC or an actual keybank; other addresses and writes stay blocked. Existing power/HOST/PTM readiness conditions remain.

Test empty, invalid prefix, invalid suffix digit, first slot valid, and last selection among multiple valid slots separately. For example, `S211MOCK000001` is only a synthetic format-test value, not an actual serial, device-model identification, or official compatibility evidence. Check rejection paths and whether cleanup is reached as well as normal fixtures. Do not modify original main or skip check branches.

The fixture had not yet been implemented at the end of this investigation. It was independent work that could proceed without requiring or reading an actual OTP/factory backup. Mark synthetic profile selection and lack of hardware verification clearly in later original runs too.

The later [synthetic INFOC slots](otp-synthetic-serial-slots.md) implemented this fixture as explicit opt-in. The previous sentence was a plan at the end of this investigation; unverified boundaries for actual data, cleanup, and full initialization remain.

There was no glasses scan/connection, RAM payload, OTP/fuse/security/MRAM write, OTA, or flash. Full factory initialization, whole boot, integrated display, and physical installation/recovery remained incomplete; product completion stayed 13/29, 44.8%.
