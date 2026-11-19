# Original erase timeout on non-FF NOR and fresh-process initialization

bw391. The first KV formatter erase from stock 2.4 actual ARM main reset was deferred. **Poll failure 1 → NOR error 4 → adapter 0 → partition 0 → FlashDB success 0**, preservation of non-FF NOR, and strict stop on a subsequent busy read were confirmed. Passing only completed NOR to a fresh process with fault off let the original formatter reach the existing main wait point, matching normal NOR/full SRAM. Full E08, recovery of existing user data, and full boot remain incomplete; overall 6/16=37.5%.

## Input and change boundary

KV/NV window starts at 0x1fc0000 and is 0x40000 bytes. The first 4096 bytes repeat 00..ff sixteen times; the rest is FF. The first sector has 4080 non-FF bytes. LittleFS window remains FF. This is explicit synthetic input, not a physical device dump, personal settings, or owner data. Unlike an incomplete erase of an already-FF sector, it can check data preservation.

Original main/vector/branches/returns/TCB/SP/IRQ were unchanged. Source initial SRAM/ITCM fill was retained and only NOR loaded at CPU instruction 0. SRAM before/after loading was checked against existing A5 fill. This is the original formatter from main reset, not a caller inserted after boot initialization. It is not boot from actual ROM/bootloader.

The NOR model used existing `sectorEraseMicroseconds:1000` and `completeSectorErase:false`; no new erase device was implemented. 1000 µs is an assumption, not a physical measurement. The model turns a whole sector FF at timer completion, so partial-bit erase/physical power loss are not guaranteed. The pinned GAF profile was also connected, but fault stopped before IMU initialization.

## Observation and controls

An optional first-erase-only mode was added to existing `BlackwallNorErrorObserver`. Default program mode remained; existing five-argument and new six-argument calls were separately confirmed compatible in actual Renode (ARM executions 0). After first erase starts, original poll/NOR/adapter/partition/FlashDB return PCs are observed. Host does not change original R0 or inject success returns.

| Run | Erase started/completed | First return chain (poll/NOR/adapter/partition/FlashDB) | Result |
| --- | --- | --- | --- |
| Normal, observation off | 136/136 | Not collected | Main wait PC 0x5542c6 |
| Normal, observation on | 136/136 | 0/0/4096/4096/0 | Same wait point |
| Deferred, observation on | 1/0 | 1/4/0/0/0 | Strict stop on subsequent busy read |
| Deferred, observation off | 1/0 | Not collected | Same stop |
| Fresh process, normal erase | 136/136 | 0/0/4096/4096/0 | Same wait point as normal on |

During deferral, program starts/completions/bytes written were 0. Entire KV/NV and LittleFS remained at initial values. FlashDB wrapper returned 0, but caller attempted to read next sector 0x1fc1000 of still-busy NOR using opcode 6c/CTRL 0x100461. guard_iom7_tail rejected a four-byte CTRL write at 0x40061000 from PC 0x4e8a46. Fault CLI exit 1 and failure to reach later main wait were retained. CFSR/HFSR and memory-policy violations were 0; protection was not disabled.

**Observer neutrality was not established overall.** Normal on/off had matching NOR before/after, return summary, and completion counts, but final SRAM differed by 270 bytes. The full diff was retained without determining all causes or excluding allowed addresses. In contrast, fault on/off were exact in full SRAM, NOR, return summary, and same strict stop. Error-return observations are therefore limited to that fault-control scope, not generalized to normal full-RAM neutrality or all inputs/observation points.

## Fresh-process response

The stopped machine was not resumed. Two completed NOR windows from the fault were copied into a separate Renode process at CPU instruction 0 with existing initial SRAM. Prior guest SRAM, pending timer, and controller state were not imported. The new input model selected normal erase completion. Restart image hash was checked against original fault output and capture lineage.

The original normally erased/formatted the same initial pattern, completing 136 erases and 270 programs and reaching existing initialization wait PC 0x5542c6. First normal erase return chain, final two NOR windows, and complete SRAM were byte-exact to normal observation on. This wait is a GAF getter-entry boundary, not completed service/app initialization.

Input was not a valid user KVDB from the beginning, so this is not called user-data-preserving recovery or full-stock restoration. It verifies timeout/no-write state in the declared virtual initialization scenario and fresh original formatter response to the same completed backing.

## Checks and tools

Forty integrated audit checks and byte-exact frozen report passed; three JSON/log/hash-consistent negatives for concealed error return, false erase bytes, and wrong reformat image were rejected. Fourteen progress-management checks passed. There were five actual ARM main runs and one separate observer-constructor compatibility test with ARM 0. Existing stuck/native material was not rerun with identical inputs; new non-FF pattern, callback observation, observation-off control, and retained-image fresh process were verified.

The first audit failed in host checking because a shared parser requiring one strict stop was also used for normal hold. Without weakening the shared parser, it was corrected to read actual BLACKWALL_REPORT directly and check guard count at each boundary. Initial post dump selected only three guard types, so it was not assumed to be the full guard list. Each capture's original main report contained all guards and verified the precise stop; subsequent dumps export the complete list. Historical inputs/outputs were not changed retroactively.

```sh
<private-python> tools/probe_boot_nor_erase.py <simulator> <normal-writer> <control-off>
<private-python> tools/probe_boot_nor_erase.py <simulator> <normal-writer> <control-on> --observe
<private-python> tools/probe_boot_nor_erase.py <simulator> <normal-writer> <fault> --fault --observe
<private-python> tools/probe_boot_nor_erase.py <simulator> <normal-writer> <fault-off> --fault
<private-python> tools/probe_boot_nor_erase.py <simulator> <normal-writer> <restart> --observe --retained <fault>
<private-python> tools/verify_boot_nor_erase.py <simulator> <new-audit>
```

Pinned evidence is private `boot-nor-erase-native-01/{control-off,control-on,fault,fault-off,restart}`, `boot-nor-erase-audit-04`, `boot-nor-erase-audit-frozen-02`, `boot-nor-erase-research-01/{manifest.json,control-ram-differences.json}`. Dataless packages used the existing verified local dependency wrapper. Frozen run/model/input/log of each capture is audited without regenerating historical dumps with the current builder.

## Remaining goals

Selected stock 2.4 program/erase timeout and atomic-completion-model preservation/fresh-reset response were confirmed. E08 still needed integrated stock 2.3/Faceclaw controls, stored-version mismatch, and interruption extent/explicit failure checks under normal user state. First record byte is not assumed to be a verified schema version. Next establish actual version checks from original structures/logs and connect existing corruption material with per-version controls. The normal-observation 270-byte SRAM difference remains unresolved evidence. E05/E06 natural app/reset and full display remain separately incomplete.

The 16 acceptance/status/evidence items and API 3/6 were unchanged. No physical device, BLE/USB/UART, flash/OTA, Astra/subagent, or external posting occurred.
