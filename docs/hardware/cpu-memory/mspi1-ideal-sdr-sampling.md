# MSPI1 Ideal SDR Sampling and Original Scan Execution

Task bw-0174. Added an explicitly selected `ideal-sdr` profile. Original main from stock 2.4, 2.3, and Faceclaw each completed a 36×32 scan and returned to the original caller. Full boot, app loop, and integrated display remained incomplete; product progress stayed 13/29, 44.8%.

## Model meaning

The default `fixed-capture` is preserved. The selected profile assumes error-free digital transfer across the three DEV0CFG bits RXCAP/RXNEG/TXNEG. It neither creates nor verifies physical setup/hold, wiring delays, or an actual timing window. Other configuration fields, commands, lengths, power, clock, and FIFO guards remain. With identity `none`, this profile also supplies no ID response.

Original ARM bytes, branches, and scan return values were unchanged. Existing virtual power/memory/clock assumptions remain, so this does not mean all actual hardware checks passed. Transfer 10 µs and NOR reset recovery 100 µs are also model assumptions.

## Execution evidence

| Observation | Each of three ideal originals | Fixed stock 2.4 control |
| --- | --- | --- |
| Completed ID reads / FIFO reads | 1152 / 1152 | 288 / 288 |
| Starts / completions including reset | 1154 / 1154 | 290 / 290 |
| Completed sampling-combination mask | F0 | 10 |
| Original pass matrix | All 36 rows FFFFFFFF | Not captured before stop |
| Original scan return | R0=0, once | Not reached |
| Original selected output, six bytes | 010000010e20 | Not reached |
| Selected observation events / dropped | 3787 / 0 | 1165 / 0 |

Masks are hexadecimal. Units tested all eight combinations of the three bits, but actual scan observed only the four with TXNEG=1. The all-pass matrix and selected output are results of the original algorithm under this ideal model, not physically optimal settings or measured margins.

Matrix addresses were derived from the actual scan input pointer and original stack frame. The tool compares initialization size 144 bytes, SP+2C indexed store, repetition-ending branch, and row pointer passed to selection helper with original instructions. Immediately after completion, three consecutive observation points read 16+16+4 words. Output is two words at the actual caller return point, using only the first six bytes. Observation hooks check instruction boundaries and do not modify CPU state.

The next ideal strict boundary is CTRL `30441` write. At that point DEV0CFG=`03010061`, INSTR=`9F`, DEV0XIP=`ED`, with turnaround changed from 8 to 0. PIO transfer with this setting was not yet allowed. Next analyze original reconfiguration and the zero-turnaround RDID contract. Flash contents and XIP backing remain unimplemented.

## Verification and preservation

Outside Git under `simulator/`:

- `mspi1-sampling-unit-02`: 51 ideal-unit checks.
- `mspi1-sampling-fixed-01`: 33 default-profile checks.
- `mspi1-sampling-none-01`: five identity-absent profile checks.
- `mspi1-sampling-regressions-01`: RDID 30 + XIP mixed 63 checks.
- `mspi1-ideal-sampling-main-01/stock24`: reused first successful stock 2.4 result.
- `mspi1-ideal-sampling-main-04`: stock 2.3, Faceclaw, and fixed control.
- `mspi1-ideal-sampling-verification-02/report.json`: 109 checks comparing current source, original main, fixture hashes, execution logs, matrix, returns, next boundary, and host waiting behavior. Audit 01's 106 checks were preserved.

Reproduce the final audit with `tools/verify_mspi1_ideal_sampling_evidence.py`. Audit counts are not product-completion rates or numbers of physical-device validations.

## Host observation failures and fix

In the first batch stock 2.4 succeeded, but stock 2.3 did not reach the strict boundary before the host's 15-second observation ended. Exit-log PC=40 was not evidence of reset; it was a decrementing delay loop written by the original to ITCM. Confirmed that execution actually ended before subsequent tests.

Changed the host to wait until the VM naturally pauses and print progress every five seconds. Attempts 02/03 then failed because the new progress output used Console/json before initialization. Preserved failure artifacts and moved imports before the loop. `verify_sampling_wait.py` reproduces the prior JSON error and confirms the current loop waits correctly for 0, 6, and 16 ticks. Final main-04 cases all stopped naturally at strict boundaries. Guest delays were not skipped and failure-report parsing was not weakened.

There was no physical glasses connection, installation, RAM execution, or persistent write. No full transcript-file audit or other model-family review was performed.

A read-only review by an agent inheriting the parent model identified missing direct comparison between raw snapshots and the report matrix. Audit 02 compares actual log snapshot addresses, 16/16/4-word counts, and reconstructed 36 words with the report. Existing raw evidence was strengthened without rerunning. Astra was not used.
