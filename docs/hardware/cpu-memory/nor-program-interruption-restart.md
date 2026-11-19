# Original NOR Program Interruption and Reread in a New Process

bw386, partial progress for E08. Distinct from static bit corruption, execution stopped while WIP was set during the sixth kvTime program started by actual original ARM. When only completed NOR was passed to a new machine, **the original selected the previous record rather than adopting the incomplete state, even though the new record's payload was entirely present**. Overall progress was **6/16 = 37.5%**, with E08 incomplete.

## Execution boundary and assumptions

Executed the existing stock 2.4 device ATT time-setting scenario unchanged. Original main, peripheral models, board, and initial SRAM/ITCM were unchanged. Added an observation hook at PC `0x47b7c8`, where the original RDSR function returns after checking bit 0. It is installed only after the initial main hold, so initial boot follows the existing path. PC, branches, returns, TCB/SP, and IRQ were not forced.

Observation is an execution-profile change. The nonstopping control passed 25 existing app checks; linked/NOR report JSON values, complete SRAM at three times, and NOR before/after were exact against the prior capture. This controls this input and checkpoint, not global proof of observer noninterference.

The existing model assumes backing bytes change at page-program completion after 1,000 µs. Pending writes are not passed to the new machine. Physical NOR partial-bit program/erase under power loss is neither implemented nor verified. Current host reset atomically cancels pending work and retains completed backing; controller power-off alone does not cancel ongoing external NOR work. Do not confuse these.

## Seven writes by the actual original

| Start order | Prior completions | Prior cumulative completed bytes | Address |
| --- | ---: | ---: | --- |
| 1 | 0 | 0 | `0x1fc0082` |
| 2 | 1 | 1 | `0x1fc0245` |
| 3 | 2 | 2 | `0x1fc0249` |
| 4 | 3 | 22 | `0x1fc025d` |
| 5 | 4 | 28 | `0x1fc0263` |
| 6 | 5 | 40 | `0x1fc0245` |
| 7 | 6 | 41 | `0x1fc0082` |

All seven were observed during actual WIP/status 1 in the normal control. The interrupted run's first six rows exactly matched control in PC, SP, and state. At interruption starts=6/completions=5, completed bytes=40, ProgramBusy=true, and original upper-app return=false. Wire transfer of the sixth write completed, but device programming had not.

The interrupted NOR already contains the entire new payload `0300000000f153651000fe58`. Only two bytes differ from the normal completed image: new state byte `0x1fc0245` is `7f` (normal `3f`), and prior state byte `0x1fc0082` is `1f` (normal `0f`). Do not infer generic state meanings from enum names; verify actual bytes and original selection results. Entire neighboring NVdb/LittleFS were unchanged during the same write interval, all changes were 1 → 0 within declared KV range, and no erase occurred.

## Selection after a new main reset

Loaded only the two NOR windows from the interrupted capture exactly into a new Renode process. Confirmed CPU instruction 0, unchanged SRAM before/after loading, exact match to existing A5 initial fill, and no transfer of prior guest SRAM. The host did not edit NOR bytes or complete pending work.

Original main read the previous `010000002b2d37682000f018` into RAM. That record actually existed in initial source SRAM and NOR before and during the write. It differs from the incomplete new timestamp record. The existing strict CPDLPSTATE 22 stop at PC `0x4956e2` was retained afterward. Probe exit 1, full boot false, and CFSR/HFSR/memory-policy 0 remain. Completion of original upper-app recovery or normal service resumption is unverified.

The first audit failed because it expected the old record already to be resaved as type 3. Actual RAM retained type 1. The oracle was corrected to require an exact match with the existing source SRAM/NOR value; no type-3 migration call is claimed. The failure remains in private `initial-oracle-failure.json`. Do not mix bw385's type-3 initial-value rewrite under corrupted CRC input with selection of the normal prior record here.

## Verification and reproduction

Sequentially executed one actual control, one interruption, and one new main reset. Passed 25 integrated audit checks, with byte-exact frozen reports, and rejected three semantic negatives that consistently modified JSON/log/hash and read results: forced promotion of incomplete state, false completion count, and false consumption of the new value. Passed 14 progress-management checks and confirmed zero remaining Docker containers after runtime exit. Model source was unchanged, so do not inflate the report by implying the same peripheral unit tests were rerun.

```sh
<private-python> tools/probe_nor_program_cut.py <simulator> <normal-writer> <new-control> --stop-program 0
<private-python> tools/probe_nor_program_cut.py <simulator> <normal-writer> <new-cut> --stop-program 6
<private-python> tools/probe_runtime_kv_restart.py <simulator> <cut-capture> <new-restart> --retained
<private-python> tools/verify_nor_program_cut.py <simulator> <new-audit>
```

The audit command uses pinned evidence paths `nor-program-cut-native-01/{control,before-valid-status}` and `nor-program-cut-restart-01/stock24`. Restart exits 1 because a later hold was not reached; the audit separately judges only the write-interruption/reread boundary. Pinned sources and full hashes are in `nor-program-cut-research-01/manifest.json`. The previous pinned local dependency wrapper was explicitly reused for dataless packages.

## Remaining E08 criteria

This experiment is limited to one program boundary in an atomic-completion model and one stock 2.4 image. Remaining work includes original selection on both sides of completion, stock 2.3/Faceclaw, erase interruption, actual busy-timeout/FAL error propagation and explicit failure/recovery, and data/version mismatch. An existing saved stuck test stopped strictly after two timeouts when reading the next sector of a busy NOR, so it is not counted as safe recovery. Do not mark E08 complete.

Next reuse the same observer, source, board, and model to compare restart selection immediately before the seventh write (new state update complete, prior-state cleanup incomplete). Then extend to stock 2.3/Faceclaw cross-runs and erase/timeout contracts. Do not rerun a control with identical inputs.

There was no physical device, BLE/USB/UART access, flash, OTA, Astra/subagent, or external publication.
