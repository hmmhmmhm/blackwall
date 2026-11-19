# kvTime Stored Schema Version and Mismatch Assessment

bw392. Original-code evidence establishes that the first kvTime byte is a **stored schema version**, not an unspecified type. All three originals expect 3. Version 4 with valid internal and external CRCs was loaded into RAM by new main executions for all three images. This is an early-checkpoint observation, not certification of the whole app or backward/forward compatibility. E08 remained incomplete; overall progress was 6/16 = 37.5%.

## Direct evidence that it is a version

`schema_contract` checks the following in actual original instructions:

- The reload function reads 12 kvTime bytes to stack+`0x10`.
- It places the value from `ldrb r0,[sp,#0x10]` and constant 3 as actual/expected arguments to the original log `version %d(%d)`.
- The producer writes 3 at record offset 0. Offset 4 is timestamp, offset 8 is timezone, and the CRC of the first ten bytes is stored at offset 10.
- If CRC fields differ, it compares the read version to 3 and skips the resave branch for 3 or higher.

| Profile | Reload | Original version log format | RAM record |
| --- | --- | --- | --- |
| Stock 2.4 | `0x57a270` | `0x7b3024` | `0x2000690c` |
| Stock 2.3 | `0x5a32d4` | `0x7c104c` | `0x20004604` |
| Faceclaw 38 | `0x5a32d4` | `0x7c104c` | `0x20004604` |

The string is connected to the original `_kvdbUpdataTime`/`service_kvdb_time.c` log. Classify this evidence as source-supported; do not claim physical-device logs were collected. Both official firmware versions above and Faceclaw expect kvTime schema 3, so product firmware version and stored schema version are not the same concept. Do not extend this to all FlashDB, other KV objects, or hardware ABI compatibility.

## 108 isolated tests of original policy

Using `--schema-matrix` in the existing checker, tested version 0/1/2/3/4/255 × equal/different CRC fields/actually valid CRC × store return 0/7 × three originals, for 108 cases. Each result distinguishes CRC-field equality from an actually correct payload CRC. The initial 72-case prototype covered equal/different fields; the final evidence uses 108 cases including actual valid CRC.

- When the CRC field equals the current RAM field, no resave occurs even for a lower version.
- When the CRC field differs and version < 3, a version 3 record is resaved using the current RAM timestamp/timezone.
- For version >= 3, this function neither resaves nor explicitly rejects even if the CRC field differs.
- The function returns 0 even if the resave API returns synthetic nonzero 7.

These are isolated Unicorn M7 tests executing original instructions/CRC with storage read/write and logging-flag ABI stubbed. They do not execute complete main/FlashDB/NOR commits. Initial RAM used records from each normal capture (version 1). This function itself does not copy the stack read payload into the global record. Do not claim that other initial restoration paths or the full actual migration were verified.

## Valid future schema input in actual main

Changed the normal writer's record to version 4 and recalculated both internal CRC16 and FlashDB external CRC32. This is a synthetic compatibility test, not a claim of official version 4 support. In a new process, only completed NOR was loaded at CPU instruction 0, using the existing A5 SRAM fill and original main. No previous guest SRAM was imported and the host did not directly populate the global record.

| Profile | Expected schema | Actual RAM record | CRC16/32 | Subsequent stop |
| --- | --- | --- | --- | --- |
| Stock 2.4 | 3 | `0400000000f1536510000444` | Valid/valid | PC `0x4956e2` |
| Stock 2.3 | 3 | Same | Valid/valid | PC `0x4897fa` |
| Faceclaw 38 | 3 | Same | Valid/valid | PC `0x4897fa` |

The stock 2.4 bw385 capture was reused after hash verification; stock 2.3 and Faceclaw each received one additional run. All three reached this early RAM-load point without explicitly rejecting the higher-than-expected schema. The subsequent unsupported CPDLPSTATE 22 stop/CLI exit 1 was preserved. Do not say that the original reload policy ran to completion on the natural path or that the entire app worked normally with this data. An observed early schema-mismatch load is separate from full version compatibility/recovery.

## Verification tools and model lineage

Added an explicit `future-record-version` mode while retaining the historical `future-record-type` alias/captures. The old audit's `damaged_record_loaded` is an internal name for classifying a modified input load; in this case the CRC is not damaged. The summary report records expected_schema 3, loaded_schema 4, and CRC validity separately.

The two new captures use bw389's default-off NOR component. The auditor does not accept arbitrary components from the current worktree; it permits only one NOR component replacement pinned by the completed bw384/bw389 manifests. Original ARM/run/SRAM/ITCM match the existing baseline, and only that pinned change must explain the profile model SHA. An unrelated timer change was rejected even when metadata/input hashes were adjusted.

The 108 frozen reports and new native three-profile audit reports were byte-exact. Existing reload 48 and existing three damaged-input audits were also byte-exact with old reports. Three negatives—changed expected-version constant, changed log label, and undeclared NOR model change—were rejected at their respective verification points. Fourteen progress-management checks passed. There were two actual new native runs and one reused capture, separate from 108 standalone ARM cases.

```sh
<private-python> tools/inspect_kvtime_reload_policy.py <simulator> <new-audit> --schema-matrix
<private-python> tools/probe_kvtime_corrupt_restart.py <simulator> <writer-capture> <new-restart> --mode future-record-version
<private-python> tools/verify_kvtime_corrupt_restart.py <simulator> <new-audit> <capture>...
```

Evidence is private `kvtime-schema-matrix-02`, `kvtime-schema-matrix-frozen-01`, `kvtime-schema-native-01/{stock23,cfw}`, existing `kvtime-corrupt-native-01/stock24-future-record-type`, `kvtime-schema-native-audit-01`, `kvtime-schema-native-audit-frozen-01`, and `kvtime-schema-research-01/{schema-summary.json,manifest.json}`. Dataless packages reused the existing pinned local dependency wrapper.

## Remaining criteria

The original data schema name, expected value, policy, and initial version 4 load were established. E08's stock 2.3/Faceclaw program/erase integration failure controls, interruption/error handling for actual user state, and higher-level recovery remain incomplete. Do not substitute a stored-schema mismatch for successful full firmware 2.3 → 2.4 migration. Since consumption/rejection after CPDLP22 is unconfirmed, overall compatibility of this combination remains Unknown. The 270-byte SRAM difference between normal erase observation on/off is not claimed resolved.

Next connect existing pinned GAF/NOR fault tools to original 2.3/Faceclaw and verify the failure paths not yet executed. Do not merely add more of the same schema/CRC combinations; close remaining execution evidence for E08. The 16 criteria/status/evidence and API 3/6 were unchanged. No physical device, flash/OTA, Astra/subagent, or external publication was involved.
