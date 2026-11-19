# NOR Program Timeout in Actual Main Runtime

bw389. **Actual original stock 2.4 main reset → device ATT → withheld completion of the first virtual NOR program → original busy-poll failure 1 → NOR error 4 → adapter 0 bytes → partition 0 → FlashDB write-wrapper success 0** was confirmed. ARM instructions/branches/returns were not changed, and no peripheral ABI stub was inserted. Full app recovery remained unknown. E08 remained incomplete; overall 6/16 = 37.5% and API screen 3/6.

## New model test option

`BlackwallMspi1PioReset.HoldNextProgramCompletion()` is an explicit fault API allowing the emulator host to withhold timer completion for the next program operation. No guest MMIO command was added. It defaults off; reset clears unused configuration, an in-progress hold, and diagnostic counts. The API is permitted only when program is supported and default completion enabled; it rejects duplicate setup and setup while wire/device busy or during erase/recovery. Completed NOR bytes remain preserved as before.

After original TX and wire completion, actual ProgramBusy/WIP remains set. The host does not directly inject an original function's failure return. Since writes use the existing atomic-completion model, backing storage does not change while held. This is not a guarantee about actual NOR power loss or partial-bit program/erase.

A nearby executable-check approach from `tdd` was applied. Hold/reset/next-normal-operation controls were first added to existing program unit tests and failed on the old model because ProgramCompletionHeld was absent. After the model change, 20 passed; existing page-program 29 and snapshot 37 also passed. These are actual Renode model tests, not physical hardware tests.

## Default off and original execution

The normal control passed the existing 25 app checks. Existing connection-report fields, full SRAM at three points, and NOR bytes before/after were exact against the existing writer. Additional pinned GAF-profile diagnostic fields were checked separately; getter/configuration consumption was zero through normal ATT return. No general claim of observer-hook noninterference is made beyond these inputs/checkpoints.

Return PCs for original FlashDB, partition, device callback, NOR, and poll were located from original instructions and the descriptor table in native SRAM. Actual rows recorded in the fault run follow. All are in the original ble_msgrx task/Thread context, with SP, TCB, and IPSR also recorded.

| Layer | Original return | Actual program starts/completions | Hold injections |
| --- | --- | --- | --- |
| Busy poll | 1 | 271/270 | 1 |
| NOR write | 4 | 271/270 | 1 |
| Device adapter | 0 bytes | 271/270 | 1 |
| FAL partition | 0 | 271/270 | 1 |
| FlashDB write wrapper | 0 | 271/270 | 1 |

271/270 is the initialization cumulative count; runtime increased by one start and zero completions. The cumulative 10,406 recorded bytes did not change. Existing KV/NV and all LittleFS were identical before/after the write, with no erase. At this point original RAM had already changed to attempted new kvTime `0300000000f153651000fe58`, but NOR did not contain that new record. Therefore RAM updates and wrapper success 0 are not durability evidence.

After wrapper return the upper app had not yet returned. A separate sensor_hub strictly stopped at unsupported request `7c000402` after reading 41 GAF fields/153 bytes and writing 225 bytes of configuration. Actual HAL PC 0x58236c/IOM4 CMD 0x40054120 and the register's transmit word were confirmed. CFSR/HFSR and memory-policy violations were zero. No response completed unsupported GAF calculation.

## Failure of an older fixture and structural prevention

Initially the older IMU model from bw384 writer was reused unchanged. Default off was normal, but the fault stopped after about 64 ms at `0x02ae` read `7c02ae00`, so NOR return rows were not obtained. This was an already resolved legacy-profile gap, not the latest GAF service boundary. The initial CLI exit 0 checked only injection consumption and was not accepted as timeout-propagation success. Saved run, model, and failure were retained.

The new run connected the verified component SHA `3ddefc4c…`, 153-byte fixture, and explicit trim 0x85 from existing bw378 `integrate_gaf`. The changed IMU component beyond NOR and board/profile declarations were checked separately. No physical trim-value claim is made. Under this profile's fault, the actual return chain was observed before reaching the currently unsupported GAF service boundary. This was verification of explicitly different model inputs, not simply restarting an existing execution for repeated observation.

`probe_runtime_nor_timeout.py --fault` now rejects without `--gaf-profile` with exit 2 before output creation. CLI success was also strengthened to require the actual four-layer return chain. Older captures are audited only against historical inputs/logs; current candidates are not retroactively applied.

## Reading in a new process

Only the two unchanged completed NOR windows from the pinned GAF fault were loaded into a new Renode process. Checks confirmed CPU instruction 0, unchanged SRAM before/after loading, exact A5 initial fill, and no transfer of previous guest SRAM. The model was the same and the new run contained no call setting the runtime fault.

The original read prior `010000002b2d37682000f018` into RAM. The subsequent unsupported CPDLPSTATE22/PC 0x4956e2 stop and restart CLI exit 1 were retained. This is not full boot, service return, or complete app recovery. It is limited to read evidence in a virtual model that does not transfer pending state to the new process.

## Verification and reproduction

Twenty-eight integration-audit checks passed, with byte-exact frozen report. Three consistent JSON/log/SRAM/hash negatives—concealed error return, false backing write, and adopting the new value on restart—were rejected, along with one legacy-fault preflight rejection. Fourteen progress-management checks passed. New native runs comprised legacy control/fault/restart and pinned GAF control/fault/restart, three each. The legacy fault is explicitly a failure without observed timeout return. Unit tests separately retain red 1, green 20, and existing 29/37 regressions. All runs were sequential; zero Docker containers remained afterward.

```sh
<private-python> tools/probe_runtime_nor_timeout.py <simulator> <normal-writer> <new-control> --gaf-profile
<private-python> tools/probe_runtime_nor_timeout.py <simulator> <normal-writer> <new-fault> --fault --gaf-profile
<private-python> tools/probe_runtime_kv_restart.py <simulator> <fault-capture> <new-restart> --retained
<private-python> tools/verify_runtime_nor_timeout.py <simulator> <new-audit>
```

Pinned private evidence is `runtime-nor-timeout-gaf-native-01/{control,fault}`, `runtime-nor-timeout-gaf-restart-01/stock24`, `runtime-nor-timeout-audit-01`, `runtime-nor-timeout-audit-frozen-01`, and `runtime-nor-timeout-research-01/manifest.json`. Legacy evidence is separate in `runtime-nor-timeout-native-01`/`runtime-nor-timeout-restart-01`. The restart builder also accepts an identical model from source already using current components and rejects unknown component combinations. It checks unique input/completed-NOR hashes during source copy. The existing pinned local dependency wrapper was explicitly reused for dataless packages.

## Remaining overall work

Stock 2.4 program timeout → lost wrapper error → unwritten NOR/new-reset selection was integrally verified. Actual original returns, damage scope, and new reset for erase failure/interruption were next; equivalent integration failures for stock 2.3/Faceclaw, storage-version mismatch, and upper-app recovery also remained. Do not mark E08 complete here. GAF calculation/natural app/E05 and CPDLP state/runtime reset/E06 were separately incomplete. The 16 acceptance/status/evidence criteria and API 3/6 were unchanged.

There was no physical glasses access, BLE/USB/UART access, flash/OTA, Astra/subagent, or external publication.
