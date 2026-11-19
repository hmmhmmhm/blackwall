# Second transfer in original BLE version query

Task bw-0277 connected the second read in the [version/NVM original contract](em9305-version-and-trim-nvm-contract.md) to a virtual SPI peer. Version fixture `04 03 02 01` is synthetic data for checking log `1.2.3.4`; it is not the user's glasses or actual controller version. NVM erase/write remain unsupported and no physical device was accessed.

## Operation

`BlackwallEm9305EventPeer` retains existing active event and first trim read by default. Only a profile explicitly specifying `versionDataHex` additionally permits packet `01 01 fd 05 00 20 40 00 04`. Four bytes of version data, status 0..255, and a preceding read fixture are required. Status alone or invalid size/range is rejected at construction.

CS commits for first and second replies are distinguished. After the first 15-byte response, write-ready/capacity/payload are traversed again to provide the second 11-byte response (`04 0e 08 01 01 fd status` + four data bytes). Command Complete credit 1 and fixed length are explicit test format, not a measured physical error-response format. The first command record is retained and the second supplied separately. Small capacity splits each packet; peer state changes only after validating the entire word.

Packets other than the exact two reads, incorrect response length, NVM opcode, and a third command are rejected. Reset does not automatically replay a consumed scenario. This is an implementation boundary before designing subsequent virtual configuration-mode/NVM transactions; it does not mean the actual trim-mismatch path is safe or unnecessary.

## Newly exposed MRAM boundary

The first stock 2.4 run printed the original version log, but the common runner rejected it due to a non-existing peripheral ReadByte warning at `0x007ff000`. This raw run is retained in `em9305-version-sample-main-01/stock24` without a success report. A later different MMIO stop was not accepted as a success boundary.

Existing main mapping runs from `0x00438000` to just before `0x007f8000`. The read is in the MRAM tail beyond it, for which the current input image has no verified data. Instead of filling with 0 or ff, an existing `BlackwallStrictMMIO` byte/word rejecting guard was added for `0x007f8000–0x007fffff`. Board registration and guard collection were applied together only to the current candidate; control retains prior configuration.

Corrected stock 2.4 blocked address `0x7ff000` as a single strict read at byte-load PC `0x484e64`. The corresponding stock 2.3/Faceclaw code location is `0x4824b0`. This is a stop without using unknown data, not normal main boot completion. Next analyze the region's caller, data provenance, and inclusion in official images.

## Original version handling

Analyzer `tools/inspect_em9305_version_transport.py` finds the actual version storage slot from a literal load in pinned source and compares saved SRAM. Stock 2.4 slot is `0x20076be4`. Successful response data is copied to that slot and a log prepared. On status error the generic read does not copy, so the previous native snapshot slot value must remain. `ffffffff` is copied but version logging skipped. Distinguishing value semantics from previous original fragment results, this run confirms storage effects on the natural main path.

## Test record and limitations

RED failed because the constructor did not accept the version option. A subsequent constructor-rejection test failed because the dynamically loaded Renode assembly type could not be imported directly in the Python namespace; only the test was corrected to pass input via the actual peer type's reflection constructor. Both failures and executables are retained. Existing success is not overwritten.

Native results, unit/regression counts, and pinned-dependency verification are recorded in the final confirmation below. All proprietary main/SRAM remains in the private simulator outside Git. Full main/BLE boot, integrated 576×288 display, and physical recovery remain incomplete. Product progress remains 13/29=44.8%.

## Final confirmation

| Input | Version slot change | Original version log | Next boundary |
| --- | --- | --- | --- |
| Synthetic `04030201` / status 0, three images | `00000000`→`04030201` | `1.2.3.4` | MRAM byte read `0x7ff000` |
| Synthetic `ffffffff` / status 0, stock 2.4 | `00000000`→`ffffffff` | None | Same |
| Synthetic `04030201` / status 1, stock 2.4 | Remains `00000000` | None | Same |
| Version feature off, stock 2.4 | Previous path retained | None | Existing write-ready boundary |

- Six final native runs and six separate saved audits passed. One initial unmapped-warning raw run remains preserved as failure. Off exactly matches previous CPU, instruction count, events, and boundary. Saved analysis confirmed SRAM/original destination/data-status effects for five normal runs.
- New component unit/regression 248 conditions: two reads 44, split at capacity 4: 67, error status 45, existing first read 25, active event 19, reset 48. Valid reflection constructor controls were included in capacity/error tests to avoid false passes from unconditional exceptions.
- Existing 123 conditions for unchanged IOM model and 2696 retention source-proof conditions were reused after rechecking input/report pins. They are not added to the new native run count.
- Private `em9305-version-transport-verification-01/manifest.json` preserves model hashes, unit files, runs/audits, first failure receipt, and 19 analyzer dependencies. Pinned-copy reanalysis `em9305-version-transport-contract-02` matched the original analysis report. The first raw failure records pre-change file hashes too.

Next confirm original callers and official-image/separate-asset provenance for the MRAM tail. Without actual data, distinguish assumptions from actual files and do not write empty values as normal device contents. Virtual configuration-mode/NVM transactions and complete controller recovery remain incomplete under the [previous contract](em9305-version-and-trim-nvm-contract.md). Do not expand existing standalone display/font verification into integrated display success.
