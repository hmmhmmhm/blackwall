# Limited transport of the first EM9305 memory-read command

Task bw-0275 added a virtual SPI peer handling packet `01 01 fd 05 88 4b f0 00 08` from the [first transmission contract](em9305-first-write-command.md). Actual EM9305 data at `00f04b88` remains unknown. Responses here are explicit test inputs, not physical measurements. No device connection, flash, or OTA occurred.

## Implementation scope

`BlackwallEm9305EventPeer` defaults retain previous active-event transmission. Only a profile with `readDataHex` supports the first fd01/read8. It distinguishes write-ready with CS low, `42 00` header and capacity, exact packet fragments, and Command Complete preparation after CS release. Response is `04 0e 0c 01 01 fd 00` + eight bytes. Credits 1/status 0 are choices for testing a success response.

Normal capacity 9 and capacity 4 are distinguished. At small capacity, the nine-byte packet splits across three frames. Invalid commands, lengths, and frames are rejected before peer changes; the next command is not automatically accepted. Specified GPIO consumer PC/argument/pad config/reset-state checks remain. Actual physical CS149/RDY117 wiring and timing are not established.

Instead of increasing cumulative IOM retention budget per command, explicit `cqRetentionPerDisable` profile supplies it once per actual enabled→disabled transition. Duplicate disable and power-off do not replenish budget in the same epoch. Transfer quiescence, existing PC/context, and external-input guard conditions remain. Existing default budget 1 and explicit budget 2 are unchanged. This model is not expanded into a physical implementation of whole-chip retention.

## Current original execution evidence

Stock 2.4 original main reset execution completed the first nine-byte command and 15-byte response once each. The successful active-event UART log remained.

| Virtual eight-byte data | Branch observed in original | Next restricted boundary |
| --- | --- | --- |
| `0000000000000000` | Trim 0→7 update log, then controller reset attempt | GPIO read PC `0x502000` |
| `8003000000000000` | Trim 7, already-updated log | Next write-ready PC `0x501676` |

After reset in the first scenario the peer is Exhausted and does not fabricate a new active event. In the second scenario, next pending packet `01 01 fd 05 00 20 40 00 04` was observed in saved SRAM. Actual value at the next address and later commands require separate analysis; this peer does not handle them. Trim 7 is not selected as the actual value or reported as a success bypassing trim update.

## Execution result collection correction

The first zero capture finished native execution but failed report generation. The source runtime inherited a RAM exporter and inserted the same exporter again. Two export records in original logs matched actual SRAM size/hash, and the two stop-guard code blocks were confirmed identical. Only the missing report was restored, without changing existing files or rerunning native. `capture-recovery.json` records all existing file hashes and reason for restoration.

The common runner removes the exact exporter declared by the source plan, then inserts only one new-plan exporter. Unknown exporters or duplicate source code are rejected. A separate audit of historical capture alone permits two identical guarded blocks, two identical records, and matching actual memory hash. Mismatched duplicate records or code/record counts fail. When source audit includes full-SRAM export, export is also included in capture pin and hash verification.

## Limitations and next steps

Actual controller data, completed BLE-stack initialization, connection, normal main boot, and integrated display are unproved. Modeling a nonpersistent read command does not authorize later firmware writes or physical execution. Next investigate the new read address and trim-0 update path's commands, reset, and persistence. Overall completion remains 13/29=44.8%.

## Final confirmation

- Six original M55 natives: zero stock 2.4, trim 7 stock 2.4/2.3/Faceclaw38, capacity 4 stock 2.4, and default feature-off stock 2.4. All passed semantic contracts. Off exactly matches prior CPU, instruction count, events, and stop boundary. Zero reused the previously completed capture.
- Six separate saved audits passed without native restart. Original RF error byte 0 and next pending packet were compared at source-derived addresses and exported SRAM. The [analyzer](../../../tools/inspect_em9305_read_transport.py) does not start a new guest.
- Component units: 254 conditions (25+39+19+48+50+21+21+31). Existing retention original ARM proof 2696 conditions was reused after rechecking input pins. Conditions at different layers are not added as native start counts.
- Exporter inheritance regression: nine RED/GREEN conditions; reviewed-source export regression: three conditions (valid export and old no-export acceptance / mutation rejection). New captures after exporter fix have one exporter block; historical zero's two blocks remain.
- Private `em9305-read-transport-verification-01/manifest.json` pins model hashes, component unit reports, six captures, restoration receipt, existing proof, and 17 analyzer dependencies. Independent results generated by pinned analyzer confirmed five saved analyses match. First source acceptance failure and zero's original collection failure were not deleted.

Related candidates: `tools/em9305-read-command-{zero,trim7,peers,capacity4}-candidate.json`. Proprietary main/SRAM and all native outputs remain in the private simulator outside Git.
