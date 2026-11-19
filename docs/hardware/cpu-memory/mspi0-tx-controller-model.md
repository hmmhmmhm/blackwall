# MSPI0 TX Controller and Natural Transfer Capture

bw-0314. Connected a limited MSPI0 transmit controller to Renode M55 execution starting at original main reset. Stock 2.4, 2.3, and Faceclaw images generated the same four commands and consumed transfer completion. External-chip receipt/behavior, full boot, and display output were not verified. Overall acceptance remained **13/29 = 44.8%, scope v2**.

## Implemented boundary

Added an explicit `tx-capture` profile to `tools/renode-mspi1-config.cs`. It attaches only when MSPI0 power, clock, and IRQ owners match; the existing default profile remains. Supported scope is SERIAL0 (chip-select 0), SDR, non-mixed PIO TX. RX, DMA, command-queue execution, and external slave state are unsupported. In bw317 the SVD enum was rechecked and earlier wording CE1 corrected to CS0. The code's DEVCFG0 value-1 check did not change.

- FIFO holds 16 32-bit words. Additional writes when full are rejected; acceptance, drain, and completion are distinct.
- Final-word padding beyond XFERBYTES is not included in payload.
- A virtual timer drains at most one word per 1 µs. Commands without data also complete after the first tick. **This time is a declared service hypothesis, not a physical SPI speed measurement.**
- STATUS completion and IRQ pending are set only after every requested byte is accepted and drained. The completion-suppressed profile does not produce these effects.
- Power or MSPI0 clock changes interrupt an in-progress transfer. An independent MSPI1 clock-field change does not cause interruption. TX busy/FIFO state is included in determining whether power-off is allowed.
- The 4 MiB/4,096-frame recording limit is a simulator resource limit, not hardware capacity.

## Original main execution results

Original code generated the following sequence for all three images. Transfer completion is supplied by the virtual controller above. No forced function return or firmware branch modification advanced execution.

| Order | Instruction | Logical payload | CTRL |
| --- | --- | --- | --- |
| 1 | `66` | None | `c1` |
| 2 | `99` | None | `c1` |
| 3 | `06` | None | `c1` |
| 4 | `01` | `10` (one byte) | `100c1` |

Each run had starts=4, completions=4, aborted=0, FIFO writes=1, shifted bytes=1. Do not label this panel pixel transfer or successful NOR reset. Prior BLE initialization's 59 commands/60 responses were also retained. Those BLE responses are controller mocks, not actual radio communication.

The next unsupported boundary is original `str r0,[r2]` writing value 3 to CQCFG `0x400602a0`: stock 2.4 PC=`0x572c2a`, stock 2.3/Faceclaw PC=`0x555cd6`. The write was rejected before state change; stored value remained 2. Merely allowing it would not implement the command queue.

## Failure conditions and control

Stock 2.4 with completion suppressed had starts=1, completions=0, frames=0. It subsequently stopped at GPIO RD3 read `0x40010410` (PC=`0x501676`; following bit 21 is GPIO117). The incomplete transfer was not captured as completed. Another task reaching this boundary alone does not establish full PIO timeout/recovery handling or safe fallback.

The control without the new profile matched prior `cpu-sleep-main-02` CPU, all observation events, and selected events. The existing INTCLR clear-all boundary also remained.

## Evidence and reproduction

Native evidence in the private simulator comprises three `mspi0-tx-main-01`, one `mspi0-tx-stuck-01`, and one `mspi0-tx-control-01` run. Five separate `mspi0-tx-saved-audit-01` audits check original images, logs, models, memory captures, and semantic contracts. Initial reports for three normal runs and the failure condition preserve the expected boundary-kind mismatch; saved audits were performed without repeating execution.

`tools/inspect_mspi0_tx_profiles.py` rechecks capture hashes, original main, stopped instructions, four frames, incomplete conditions, and default behavior match. It also compares source analysis and frozen-analysis results. Unit tests are separate controller checks using synthetic spin programs and are not counted as original main executions.

Verification assets and source hashes are recorded in private `simulator/mspi0-tx-verification-01/manifest.json`. Froze 95 Python dependencies; analysis report/inspector matched byte for byte. Passed 45 frozen TX, 24 retention-power, 33 MSPI0 config, and 33 existing MSPI1 CQ checks. Of nine models, only the config file changed; the other eight matched earlier versions.

The first frozen-harness invocation failed before native start because the ROOT/tools path was missing; execution followed after placing frozen models at that path. The first existing MSPI1 regression attempt failed compilation with an older clock-source assembly; the next source-replacement attempt stopped at input matching. The final attempt replaced only the exact clock component of that existing capture with current frozen source and passed the existing driver, board, and 33 checks. Failure directories were preserved. Original firmware and test expectations were not altered to bypass failures.

## Next work

Investigate MSPI0 command-queue enable, pause, TCB descriptors, submission, and DMA as a unit of behavior. Establish actual original queue data and consumption path before defining support, then proceed to panel packets and framebuffer integration. Do not manufacture successful unknown slave responses or pixel effects to advance.

There was no physical glasses/case access, flash, OTA, persistent write, commit, or external publication. The overall goal including web installation and recovery bootloader preparation remained in progress.
