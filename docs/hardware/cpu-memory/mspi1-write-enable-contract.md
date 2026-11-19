# WREN and the Original Next Command

Task bw-0179. Analyzed bw178's saved logs, manufacturer documentation, and original ARM instructions. The next request in all three originals is INSTR 06, CTRL C1, DEV0CFG `03010061`: a command-only TX descriptor without data. WREN had not yet executed at this stage.

Page 24 of Macronix MX25U25643G v1.1 describes setting WEL upon WREN 06 completion. Page 25 lists WEL clearing on power-up, soft reset, WRDI, and completion of several writes. Page 36 identifies WEL as volatile and QE/protection bits as nonvolatile. Page 90 requires 66 followed by 99 to complete consecutively for software reset; another command cancels reset-enable. These were read from the existing SHA-pinned PDF, not verified as physical state.

| Original function | Stock 2.4 | Stock 2.3 / Faceclaw |
| --- | --- | --- |
| WREN wrapper | `47BBC0` | `476EA8` |
| Current caller | `47BA04` | `476CEC` |

The WREN wrapper calls a transfer helper with data length 0 and instruction 6, then returns the transfer result unchanged. After checking success 0, the caller **immediately sends B7**. There is no WEL read call on this success branch. Therefore successful actual WEL verification after WREN cannot be claimed. B7's address-mode meaning and relationship with WEL require separate source analysis.

Preserve the existing immutable status fixture. The follow-up model is intended to change the WEL latch only in a separate selected mode requiring an explicit initial status with WIP/WEL both 0. Do not change the latch before WREN completes; status reads, NOP, and ID reads preserve it, and armed software reset clears only volatile WEL. Do not infer unknown NV bits as actual values or allow program/erase alongside it.

`simulator/mspi1-write-enable-contract-02/report.json` outside Git, from `tools/inspect_mspi1_write_enable.py`, uses 32 checks to verify manufacturer source, three originals' bytes, actual descriptors, stack caller addresses, WREN wrapper, and the next B7 success branch. Initial 01 failed because its PDF check expected incorrect wording for the actual phrase `is a volatile bit`. The PDF was not changed; 02, corrected to the original wording, is final evidence.

This was static analysis, not a new main execution, WEL transition, full boot, display, or physical device verification. Overall progress remained 13/29 (44.8%). No glasses scan, connection, RAM execution, flash, or persistent write occurred.

An inherited-parent-model read-only review also reported no material offset or interpretation errors. WREN completion is distinct from original WEL verification. No Astra, other model-family review, or full transcript-file audit was performed.

The optional model and actual original transfer completion from subsequent bw180 are recorded in [WEL model execution](mspi1-write-enable-model.md). “Had not yet executed” above describes bw179's static-analysis scope.
