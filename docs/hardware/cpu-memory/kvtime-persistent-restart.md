# kvTime Persistence in Virtual NOR and Reread After New Main Reset

bw384. Met E07's existing acceptance criterion for original stock 2.4, stock 2.3, and Faceclaw 38. Verified **actual ARM device input → kvTime program → NOR retention → new-process main reset → original reread**. Completing subsequent boot, runtime reset, storage failure/interruption, and version mismatch remain separate unfinished work.

## E07 criterion and evidence

| Existing requirement | Actual verification |
| --- | --- |
| Data written by original firmware to virtual MRAM/NOR | Existing ATT time setting → original BLE/app task → FlashDB/FAL → existing NOR PIO path in three originals. Seven programs/42 committed bytes per image, 37 physical bytes changed. |
| Original read after restart | Copied only two source NOR windows to a new Renode process. Loaded at CPU instruction 0; SRAM was byte-exact with original A5 initial fill. Original reread the 12-byte kvTime after main reset. |
| Write/erase range and neighbor preservation | During the kvTime write interval, erase 0/pending 0; all bit changes were 1 → 0 inside the KV partition. Entire neighboring NVdb and LittleFS bytes were unchanged. |
| Original input files unchanged | Verified existing main SHA, read-only input, and capture-input hashes. No prior guest SRAM was imported into the new machine. Preserved source files were unchanged. |

E07 is the acceptance criterion for the selected kvTime persistence scenario. It does not certify every MRAM function, every stored object, physical power-loss endurance, or physical flash. Baseline acceptance and denominator 16 were unchanged.

## Stored record

All three images had raw record `0300000000f153651000fe58`, timestamp 1700000000, zone 16, and CRC16 `0x58fe`. The new FlashDB KV is named `kvTime`, value length 12, total length 42; header/name/value CRC32 also matched an independent calculation. New payload is at NOR `0x1fc0263`. A string occurrence alone was not called successful storage: actual program counters, completion, bit changes, structure, CRC, and reread by new ARM execution were checked together.

Callers such as `50bd7a → 577976` are stock 2.4 addresses. `kvtime_layout.py` checks original producer instructions/literals, kvTime key, and DB stride `0x8ac` in each of three mains to find actual record/database addresses. It does not force stock 2.4 addresses onto stock 2.3/Faceclaw. Structures correspond to pinned public FlashDB/FAL source, but the exact upstream version linked into G2 was not identified.

## Restart model and scope

`BlackwallNorReadWindow.LoadCommittedImage` copies an exact-size image once into a window not yet read or written. It owns data separately from the input array; reset does not grant reinjection permission. Loading after read/program/erase, duplicate loading, and incorrect lengths are rejected. Reset preserves already committed NOR bytes. No guest interface calls the loader.

Runner loading happens only before CPU execution. Existing SRAM/ITCM initial fill and original main are used; only input NOR is retained. Complete SRAM equality before/after loading was checked. Original instructions, branches, returns, PC/TCB/SP, and hardware checks were unchanged. Controller and byte storage are virtual models; 1 ms program/erase remains an explicit prior assumption.

A new-model control without snapshot loading passed 25 existing app checks; linked report values, full SRAM at three times, and NOR before/after matched the earlier run. Addition of the storage loader alone did not alter existing behavior to pass.

After restart, firmware also performed additional KV/LittleFS writes of its own. Neighbor invariance above applies **during the selected kvTime write interval**, not the entire boot. Initial images passed to the new process had hashes exactly matching the previous commit files.

## Successful reread and subsequent boot failure

All three restarts read kvTime into original SRAM records, but did not reach the planned IMU getter hold. The existing strict guard rejected CPDLPSTATE (`0xe001e300`) value `0x22` writes at stock 2.4 PC `0x4956e2`, and stock 2.3/Faceclaw PC `0x4897fa`. ARM CFSR/HFSR and memory-policy violations were 0. This CPU power configuration was not yet supported. The guard was not relaxed and no branch forced; probe exit 1 and full-boot=false were preserved.

Therefore distinguish **completed E07 storage/reread** from **incomplete E05/E06 boot and service/runtime reset**. A correct RAM record alone does not complete whole-app boot or sleep/wake.

## Checks and reproduction

- Passed 37 new snapshot checks and existing additional-window 31/page-program 29 regressions.
- Passed 25 existing app checks for each of three actual writer runs. Preserved one no-new-component control and three restarts separately.
- Rejected four negatives consistently modifying JSON/log/hash: retained-image change, importing previous SRAM, incorrect reread value, and neighboring NVdb write.
- Saved reports for three images from the pinned checker were byte-exact.
- The first .NET comparison-type import failure was preserved as a tool error with zero ARM executions. Fixed by checking bytearray comparison first; original firmware was unchanged.

```sh
<private-python> tools/probe_runtime_kv_commit.py <existing-time-capture> <new-write-capture>
<private-python> tools/probe_runtime_kv_restart.py <simulator> <write-capture> <new-restart> --retained
<private-python> tools/verify_kv_persistence_cycle.py <simulator> <new-audit>
```

The restart command currently exits 1 because the later hold was not reached; the final audit separately decides pass/fail of the persistence cycle. Pinned private evidence: `runtime-kv-commit-native-01/{stock24,stock23,cfw}`, `runtime-kv-retained-restart-02/{stock24,stock23,cfw}`, and `kvtime-persistent-verify-all-02/report.json`.

## Environment issues and evidence preservation

Preserved execution-preparation/audit failures from insufficient disk and Docker-engine stoppage. After engine recovery, checked that no container used the same output mount and verified prepared input hashes before proceeding. No new execution was started while an actual execution handle was live.

Identical initial assets/SRAM results from this work and the Blackwall simulator were shared using APFS COW. Paths, content hashes, and file independence were preserved; hardlink fallback was 0. Original firmware and device backups were not discarded. Some workspace Python source was OS-dataless, so it was not overwritten; the previous frozen `blackwall_package.py` SHA `0e68e622…` was explicitly used. Paths, full hash, and execution wrapper were recorded in a private research folder. This is not treated as completion of E16 fresh-environment setup.

Proprietary images, SRAM, and NOR are outside Git. There was no physical access, flash, OTA, external publication, or subagent invocation. Overall progress was **6/16 = 37.5%**, separate from API display 3/6. Next investigate E08 storage error, intermediate interruption, and version-mismatch contracts, and retained-boot CPU power configuration/wait/return contracts.
