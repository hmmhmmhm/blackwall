# MSPI0 First PIO Command, FIFO, and Completion Contract

bw-0313. Verified the three original main/SRAM/GPR inputs and saved audit from bw312 to analyze the first blocking PIO command, buffer, wait, and IRQ restoration. Peripheral models and the natural-main endpoint were unchanged. Overall completion criteria were **13/29 = 44.8%, scope v2**.

## Actual first request and subsequent calls

The first request is TX, instruction `0x66`, send-instruction=true, send-address=false, data bytes=0. Original code prepares CTRL=`0xc1` and a timeout argument of 1,000,000. There is a buffer pointer, but the first request writes no FIFO data. Do not describe this as successful pixel transfer or confirmation of an external chip reset.

Compared the actual stack's blocking HAL → driver wrapper → command API → upper initialization caller using original BL instructions, prologues, and frame sizes. Subsequent static calls are below. These are **values prepared by the caller**, not proof that all corresponding bus transfers executed.

| Order | Instruction | Data bytes | Prepared data |
| --- | --- | ---: | --- |
| 1 | `0x66` | 0 | None |
| 2 | `0x99` | 0 | None |
| 3 | `0x06` | 0 | None |
| 4 | `0x01` | 1 | `0x10` |

The external chip and meaning of commands in this pattern remain unknown. Do not assign NOR or panel reset semantics arbitrarily. Distinguish an SPI master's transmit completion from evidence that an external chip accepted a command and changed state.

## Observed order of original blocking transfer

Executing original ARM at the current stop shows this sequence:

1. Write `0xffffffff` to INTCLR. Distinguish the SDK clear-all command from the public 14-bit mask.
2. Start an instruction-only transfer with CTRL=`0xc1`.
3. Since byte count is 0, the TX FIFO helper returns without accessing data.
4. Wait for CTRL bit 1 STATUS.
5. After success or timeout, clear all INTCLR and restore the prior INTEN mask.

With a declarative fixture where CTRL.STATUS is ready, the original native timeout argument was retained and the result was 0. A timeout=0, STATUS-not-ready fixture returned 4. Cleanup order was checked with varying IRQ status and restore masks. Variations of START/BUSY bits other than STATUS are inputs to determine which bits are used, not a claim that all combinations are physically valid.

With native timeout and not-ready status, the original advanced only to the boundary where it calls the 1 µs delay function. That delay/ROM path was not replaced with a stub or forced return, and actual delay time and physical completion were not verified.

## FIFO data length, padding, and error handling

Also executed the original TX helper required by the subsequent one-byte request in isolation. Tested lengths 0–8, declarative TXENTRIES values 0/15/16, and mixed responses.

- The helper reads `ceil(byte-count/4)` **32-bit words** from the buffer and writes them to TXFIFO. The final word can include caller padding beyond the logical length. Only controller XFERBYTES should be interpreted as actual payload.
- After writing each word, it waits until the low six TXENTRIES bits differ from 16. Do not interpret this as a count of free bytes.
- It proceeds to the next word even if the first wait times out. With a two-word input and declarative response 16 → 0, the final result 0 was observed to hide the earlier timeout. Do not use this as evidence of safe acceptance of transmitted data.
- FIFO samples are fixtures collecting original write attempts and return values, not an actual capacity/shift engine. An actual controller model must distinguish additional writes to a full FIFO, amount of accepted data, drain, and command completion.

A separate NumBytes=0 input with the buffer changed to an unmapped address also finished without accessing it. Conversely, a positive length requires backing storage suitable for the API's `uint32_t*` and word reads. Do not provide only one byte of memory for logical length 1.

## ABI and evidence

The original uses direction as a byte at offset 6, instruction as a halfword at offset 14, and buffer as a pointer at offset 20. Compiled the pinned SDK PIO structure for ARM32 using `-fshort-enums` and compared size 24 and field offsets. This combination matches the observed ABI; **it does not establish the actual firmware's complete build options**. Do not apply the host's default enum size unchanged.

Compared pinned [Ambiq MSPI source](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_mspi.c), header, and SVD/header masks. Actual byte accesses and control flow in the original binary are the final authority.

## Reproduction and next work

The tool is `tools/inspect_mspi0_first_pio.py`. One analysis contains 57 blocking/IRQ scenarios and 84 FIFO scenarios across three originals, totaling **141 ARM scenarios**. Unicorn M7 uses saved GPR/full SRAM, explicit status/IRQ/FIFO inputs, and caller variants. Do not report these as actual main boot counts or hardware success rates.

Reports/inspectors from final original analysis 05 and frozen 06 match byte for byte. Python 92 checks, SDK/ABI compilation, inputs, and results are pinned in private `simulator/mspi0-first-pio-verification-01/manifest.json`. Nine models and the main execution endpoint remained unchanged; there were zero new native main runs. An initial misinterpretation of API frame push/sub splitting was fixed by verifying actual total frame size; failures and intermediate results were preserved.

Next, connect interrupt clear-all and **TX controller, word buffer, logical payload, FIFO drain, completion, and power lifetime** as a unit. Do not copy MSPI1 NOR storage semantics to MSPI0. Do not treat RX data, unknown slave behavior, DMA, or pixel output as arbitrary success. Capture transfers generated by natural main, then establish the connection to external device commands and framebuffer.

There was no physical glasses/case connection, flash, OTA, persistent write, external publication, or commit. Full boot, app loop, display, and physical recoverability remained unverified.
