# BLE Key DB and Automatic Recovery Contract at the End of MRAM

Task bw-0278. Analyzed actual native context and original code at the [boundary after version query](../communication/em9305-version-read-transport.md). The first read at `0x007ff000` was a **BLE key database slot check**, not a simple firmware constant lookup. No glasses, keys, or backups were newly collected. Actual current contents remain unknown.

## Actual boundary and identification in the original

| Image | Byte load | Actual caller's BL | Slot-check function |
| --- | --- | --- | --- |
| Stock 2.4 | `0x484e64` | `0x4845e2` | `0x484e62` |
| Stock 2.3 / Faceclaw 38 | `0x4824b0` | `0x481c2e` | `0x4824ae` |

Saved original M55 R0 was `0x7ff000`, R6 was first slot index 0, and LR matched the caller return address in the table. Confirmed caller literal base, `index << 8`, and loop limit 10. Slot stride is 256 and checked range is `0x7ff000–0x7ff9ff`. Do not describe the entire 32 KiB covered by the guard as the whole key DB. The confirmed range is ten slots; the remaining tail's role is unknown.

Stock 2.4 caller entry is `0x4844a0`. ROM strings include `_AppDbHealUninitSlots`, `ble.smpdb`, `keydb heal: slot[%d] uninit fill=0x%02x -> zeroing`, and the vendor path `third_party/cordio/.../app_db.c`. This is **identification based on names and data flow in the original binary**. It does not claim identity with the same function/version in public upstream. Public searches did not obtain the vendor function's source, and other code was not substituted as equivalent original source.

## Differences between empty states and write intent

The original uniform helper compares the first byte with the remaining 255. It returns 1 if all match, otherwise 0. An optional output pointer receives 256 or the first differing index. This is not merely an all-FF check.

| Synthetic slot | Original caller's next branch |
| --- | --- |
| Uniform 0 | Move to next slot |
| Uniform nonzero such as ff or a5 | Uninitialized-slot recovery path |
| Nonuniform | Separate record validator |

The recovery prefix actually calls memset to zero a 256-byte scratch buffer. Two fragments of the write helper prepare to pass the first and second 128 bytes of the same slot to the write wrapper as 32 words each. Arguments were compared for slots 0 and 9 in all three images. Generic wrapper constant `0x12344321` is not a device secret key. These are MRAM-write-family calls, but this test **stopped before calling the callee**. It is not evidence that actual MRAM programming, ROM services, lock/yield, or the whole recovery function executed.

The validator for nonuniform records checks whether bytes at offsets `0x30/0x2f/0xc3/0x31/0x32/0x4f/0x86` are less than 2, offset 6 is less than 4, and the upper nibble of offset `0x2e` is 0. Isolated tests of the listed conditions passed. This does not verify complete record integrity, cryptographic-key validity, or cross-version ABI compatibility. Field names were not invented without an upstream typedef. Invalid records proceed to a separate caller diagnostic/recovery branch; its full behavior requires further analysis.

## Scope of obtained OTA files

Reparsed SHA-pinned stock 2.3/2.4 and Faceclaw 38 bundles. Used the existing file checker to verify 18 component CRCs in total and main preamble/vector/boundaries. Each bundle has a closed six-component table—codec, BLE, touch, case, boot, and main—with no separate Apollo tail segment. Each actual raw main ends before `0x7f8000` and supplies no data for `0x7ff000`.

This is the **known mapping scope of the three bundles currently obtained**. It does not mean all official distributions/device backups were searched, or that coincidentally matching byte patterns in another payload can serve as a key DB. Do not map another MCU's payload into Apollo MRAM. There is no basis to reconstruct the original tail as official main padding or arbitrary 0/ff.

## Execution and evidence

Actual isolated ARM execution in `tools/inspect_mram_keydb_contract.py` comprises per image uniform 12 + caller branches 5 + validator 11 + write arguments 4 + zero prefix 1 = 33 conditions, totaling 99. Original functions/fragments run on M7 with synthetic entry, registers, stack, and slots, stopping before actual logger/lock/write calls. No memory-write observer, success stub, or forced branch was used. This is not a new natural M55 main execution.

Private simulator `mram-keydb-contract-01/report.json` records source, actual native context, bundle mapping, and 99 conditions. The initial checker incorrectly specified the relative location of a message literal, failing identification; it was corrected to the actual load location. An initial dependency-count assumption also failed by counting an already-included parser twice; the actual pinned list has 20. These were checks before output-directory creation, not weakened conditions to allow false key DB identification. Final literal content and existing caller/address must match.

`mram-keydb-verification-01` pins the analyzer, dependencies, material pins, and failure-cause notes; the pinned copy's `mram-keydb-contract-02` is confirmed identical to the original report. Existing peripheral models were unchanged; there was no new native main, device access, or MRAM write.

## Next model and installation/restoration implications

The original tail may contain device-specific pairing material, so do not use copies of unknown provenance. When introducing a virtual DB, separate:

1. The default profile with no data remains blocked.
2. An explicit virtual unpaired/zero-slot profile is not treated as an actual key DB or stock device state.
3. A separate uniform nonzero/uninitialized profile must verify original recovery writes in virtual storage. Passing only zero does not support this path.
4. Reads/writes outside these slots and keys of unknown provenance remain rejected. New key generation, pairing, and persistence are not automatically allowed.

On physical devices, separately verify original key DB preservation, record compatibility between CFW and stock, and possible key loss/re-pairing during recovery. Do not promise restored pairing state merely because main/boot were restored. Shared source fragments alone do not establish key DB ABI compatibility across all three firmware versions. Approval scope for actual reads, backups, and writes is separate from this file analysis.

Product progress was **13/29 = 44.8%**. Full main, 576×288 display, and physical recovery remained incomplete. Separate EM9305 NVM transactions and restoration also remained unfinished work under the prior contract.
