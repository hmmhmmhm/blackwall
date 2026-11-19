# UART0 power request after font diagnosis

Work bw-0221. In three original images, `0x40021004 ← 0x600` is a read-modify-write adding UART0 request 200 while preserving existing UART1 request 400. UART0 base is 40039000, IRQ 15. The existing adapter supports module 0, but the current board registers only UART1/2/3.

## Original table and SDK ABI difference

Stock 2.4 power-enable function is 494ca0, write 494d78; 2.3/CFW are 488db8 and 488e90. Actual stack contains enable address 40021004, mask 200, status address 40021008, and status mask 1e00. UART wrapper reads module 0 at handle+28 and passes **module+11** as power enum. Entries 11–14 in original lookup have UART0–3 enable masks 200/400/800/1000 and common status mask 1e00.

In the public enum of reference SDK `61b293a49db34030c545f99101f7ebf6a3050314`, UART0 is **9**. Passing that value to the original function does not mean the same device. Original wrapper/lookup and MMIO masks were independently compared. Public HAL/SVD are references for register semantics, not claimed to have the same enum ABI as the original.

## Common power-status contract

Original code checks status with 5 µs budget, address 40021008, mask=expected=1e00, equality=true. The comparison is `(status & 1e00) == 1e00`; only some bits set is not success. Public HAL HCPA status mask also groups four UART bits.

The existing model ORs only individual logical status bits for each UART. This assumption does not sufficiently model HCPA common status. Simply adding UART0 to make status 600 still does not satisfy the original poll. UART wrapper does not immediately check the power-enable return, so subsequent code execution alone must not be interpreted as successful power polling. Earlier independent UART model “status bit response” remains a digital assumption within this limit.

Original poll function ran standalone with synthetic statuses 0, 600, and 1e00 and zero budget. Each of the three images returned 4, 4, and 0 respectively, nine cases total. Original internal branches/returns were unchanged; budget 0 takes a path where original does not call delay. This is not a measurement of original 5 µs waiting time or hardware HCPA response.

`tools/inspect_post_font_uart0.py` checked pinned HAL/header/UART source/SVD, existing native inputs/state, and original lookup/caller/poll in 57 checks. Evidence: `simulator/post-font-uart0-contract-02/report.json`. First inspection failed by placing the poll-instruction relative offset two bytes incorrectly; it was corrected to actual disassembly AND/CMP positions. Neither original nor reference files were modified.

## Limits for the next model

No new UART0 implementation is needed. Register the existing module 0 adapter and verify an explicitly selected HCPA common-status profile. Distinguish individual enable requests from common physical-status assumptions, and test disabling one UART while others are on as well as disabling the last. Do not silently change the default independent model.

Actual hardware HCPA delays/interactions remain unverified. A new model must also be an explicit source-based digital assumption. This work is source/existing native observation and standalone function testing; no new main run or device access. Overall progress 44.8%; normal fonts and integrated boot/display remain incomplete.

Follow-up implementation and original execution are recorded in [bw222 UART0/HCPA profile](../communication/uart0-hcpa-status-model.md). Native execution confirmed actual independent-status timeout and wrapper ignoring its return. A changed CFW storage segment under the HCPA profile was also preserved with its cause unknown.
