# Optional WEL Latch and Original WREN Execution

Task bw-0180. Added an optional WEL latch to virtual NOR. Stock 2.4, 2.3, and Faceclaw original main completed WREN transfer and returned to the original caller, then stopped at the next B7 request. Full boot, app loop, and integrated display were incomplete; product progress was 13/29, 44.8%.

## Model boundary

`emulateWriteEnableLatch` defaults to false. Existing immutable status and fixed busy-error inputs remain. Option true requires MX25U25643G identity and an explicit status seed with WIP/WEL both 0. Unknown or initially busy/WEL=1 states are rejected during creation in this limited mode.

`StatusByte` is the seed to retain; `CurrentStatusByte` is the read response. WEL is not changed before transfer completes. When supported command-only WREN 06, CFG `03010061`, CTRL C1 completes, set WEL; RDSR reflects bit 1 while preserving other seed bits. `40` becomes `42`, and `FC` becomes `FE`. All values are hexadecimal.

RDSR, NOP, and repeated WREN preserve WEL. NOP cancels only reset-enable. Unarmed 99 does not clear WEL; when 66 followed by 99 completes validly, WEL is cleared and the existing 100 µs model recovery begins. Owner reset also clears WEL and any in-progress transfer. Seed NV bits are retained. Incomplete transfer or clock-change abort does not set a new WEL. These digital abort behaviors do not guarantee state under actual electrical interruption.

Unimplemented commands including WRDI, program, erase, status write, and B7 remain blocked by guards. NOR contents, a general NV register state machine, and completion transitions for busy operations were not implemented. Seed and transfer 10 µs/recovery 100 µs are virtual inputs/timing assumptions, not physical observations.

## Original main execution

| Condition | WREN completions | Virtual current status | Original wrapper/caller returns | Next strict request |
| --- | ---: | --- | --- | --- |
| Stock 2.4 / option true | 1 | 42, WEL 1 | Both 0 | B7, CTRL C1 |
| Stock 2.3 / option true | 1 | 42, WEL 1 | Both 0 | Same request |
| Faceclaw / option true | 1 | 42, WEL 1 | Both 0 | Same request |
| Stock 2.4 / option false | 0 | 40, WEL 0 | Not reached | Existing 06, CTRL C1 |

Each of the three option-true images had 336 selected observation events, zero dropped. There were 1,157 transfer completions, 1,153 ID, one status, and 1,154 FIFO. The previous idle path's 334-event prefix, scan matrix, and selected output snapshots were unchanged. Option false stopped at the same boundary as before.

Read-only observation points were placed at the WREN wrapper's actual return instruction and the instruction after the caller's BL. Stock 2.3 and Faceclaw used the same model, board, and runtime apart from original length. Original bytes, branches, return registers, and delays were unchanged. Execution starts at main reset under existing virtual memory/power/clock assumptions; this is not full ROM boot or passing a physical device check.

The original does not directly read WEL on this path. **Original WREN transfer completion and return were confirmed, but original WEL readback success was not.** The RDSR transition returning 42/FE was verified in separate native model unit tests.

## Verification and preservation

Under `simulator/` outside Git:

- `mspi1-write-enable-unit-01`: red evidence because the old API did not accept the option. Distinguish this from testing actual WREN transfer rejection.
- `mspi1-write-enable-unit-02`: harness failure importing Renode's dynamic C# class via a Python namespace. Fixed the harness to use the existing instance's `type(q)` constructor without changing production.
- `mspi1-write-enable-unit-03`, `mspi1-write-enable-nv-unit-01`: 36 checks each for seeds 40/FC. Covered WREN completion timing, RDSR, reset, NV bit retention, repetition/NOP, abort, unsupported commands, and unsuitable seed rejection.
- `mspi1-write-enable-disabled-unit-01`: four default-option rejection checks.
- `mspi1-write-enable-stuck-unit-01`: 14 incomplete-transfer checks.
- `mspi1-write-enable-regressions-01`: existing fixed status 22, busy fault 22, NOR reset 26; 70 total.
- `mspi1-write-enable-main-01`: three originals and disabled control, four combinations.
- `mspi1-write-enable-verification-01/report.json`: 143 checks of current source, original bytes, fixtures, raw markers, original returns, next descriptor, default boundary, and prior idle prefix.

Unit checks total 90; test counts are not added to product completion. Next analyze B7's address-mode/WEL relationship and subsequent original use. This is not authorization to unconditionally allow that command or write actual firmware. There was no physical scan, connection, RAM execution, installation, or persistent write.

An agent inheriting the parent model reviewed production, tests, the 143-check audit, and four main results read-only and reported no additional material defects. Do not extend the result to original WEL readback, physical state, or successful NV changes. No Astra, other model-family review, or full transcript-file audit was performed.
