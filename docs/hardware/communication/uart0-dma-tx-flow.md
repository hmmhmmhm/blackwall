# UART0 SRAM DMA transmission and original completion IRQ

Task `bw-0231`. Instead of extending individual registers, transfer setup → actual SRAM-byte delivery → completion state/IRQ → subsequent transfer were checked as one operation. Original stock 2.4/2.3/Faceclaw opcodes, PC, branches, and function returns were unchanged. No physical glasses were accessed.

## Source contract

Existing pinned UART HAL/SVD and three original TX configuration functions were compared. Twenty-six checks in private `simulator/source-model-uart-dma-01/source-report.json` and three standalone original-function runs confirmed:

1. Stop previous DMA with DCR 0.
2. Store byte address in TARGADDR (+4c), length in COUNT (+50).
3. Allow IER DMA complete/error bits 1800 and clear IEC 1821.
4. Clear RSR DMA state 30 and, after DMB, start with DCR a (TXDMAE 2 + priority 8).

COUNT is 12-bit, maximum 4095 bytes. TARGADDR accepts unaligned byte addresses. RSR DMACPL is 10 and DMAERR 20; DMA complete/error IRQs are 800/1000. Original IRQ15 function reads masked state, clears causes, then distinguishes completion/error. This source execution is distinct from full main execution.

## Optional model

`BlackwallUartDmaTx` is explicitly connected to UART0 adapter; by default it is not connected. Only module 0 with IRQ and DMA masks enabled is allowed, and the current profile supports TX from SRAM 20000000..20380000 only. Do not expand this to other ports, RX, or arbitrary DMA addresses.

- `sram-tx-complete`: validates full range, length, UART configuration, and capture capacity first. It reads actual SystemBus SRAM bytes into the existing PL011 transmit path, then generates DMACPL/complete IRQ after all are delivered. Packets are not replaced with constants and empty transfers do not return success.
- `sram-tx-stalled`: records configuration and start but produces no bytes or completion IRQ. Active reconfiguration is blocked and DCR 0 cancellation checked.

Completion IRQ latch and RSR state are separate; software clears causes. Active configuration changes, out-of-range, zero-byte start, RX, and unsupported controls are rejected. Public HAL priority-only 8 configuration followed by target/count storage is also allowed. Priority does not mean bus contention is reproduced.

This is an **instant transfer assumption** using existing PL011 instant-empty transmission and coherent SRAM. Actual DMA delay, FIFO speed, power, bus arbitration, RX, and device error responses are neither verified nor implemented. Powerdown/reset and failure/cancellation are not counted as successful transfers.

## Original main results

The common candidate runner/plan replaced only the root component by pinned SHA and added a DMA component. Guest observation points were unchanged. `uart0-dma-tx-diagnostic.json` specifies pause/snapshot after 45 seconds of host observation rather than unlimited execution. This is a **bounded diagnostic, not normal boot or native strict stop**. PC/registers were not forced and IRQ was not forcibly cleared.

| Original | Completed transfers | Transmitted bytes | Original UART0 completion IRQ | End-of-observation state |
| --- | --- | --- | --- | --- |
| Stock 2.4 | 7 | 269 | 7, active vector 31 confirmed | Repeated UART2 IRQ17, PC 57ae94 |
| Stock 2.3 | 7 | 265 | 7, active vector 31 confirmed | Repeated UART2 IRQ17, PC 57c4c0 |
| Faceclaw | 7 | 265 | 7, active vector 31 confirmed | Same UART2 state |
| Stock 2.4 DMA-unconnected control | 0 | 0 | 0 | Previous TARGADDR strict boundary; all CPU, instruction count, and events identical |

All three extended runs retained the previous observation-event prefix. Transfer source buffers were 2035cc60 for 2.4 and 20377740 for 2.3/CFW. The original proceeded to subsequent transfers after the first 25-byte packet. Total bytes read per transfer matched actual UART capture; seven stock 2.3/CFW transfers were byte-identical.

These are original bytes observed on internal UART. First prefix 01 80 differs from magic AA in `even-g2-protocol` BLE documentation. They were not interpreted as BLE wire or official-app connection success, and the existing BLE decoder was not applied unchanged. No RX or actual peer response was supplied.

## Newly exposed UART2 issue

At bounded snapshot, UART0 IRQ was clear while UART2 raw/masked TX20, IRQ high, active vector 33, and repeated entry were observed. UART2 transmitted 0 bytes. Native MMIO/system/memory guard violations were 0, but this is not normal idle or a normal app loop.

Pinned Renode PL011 source has compatibility behavior forcibly setting TX interrupt on UARTEN. Its comment distinguishes normal threshold behavior from enable behavior for some software. The next unit checks whether UART2 restore/ready order and this behavior cause repetition. This task did not remove the quirk or forcibly clear IRQ. Actual Apollo UART event timing is unverified.

## Verification and preservation

- Default adapter TDD red failed because TARGADDR was unsupported.
- HAL-order red reproduced and fixed rejection of target after priority-only configuration.
- Final synthetic unit 44, stalled 30, and default UART regression 117 checks. Run `verify_uart_dma_tx.py` with a new output path and `--stalled`, `--regression`.
- Three final original bounded captures and one native exact control are in `uart-dma-tx-bounded-02/`, with previous source/runtime/input/hash and candidate plan and runner copies.
- Final 67-check audit is `uart-dma-tx-verification-01/report.json`; reproduction code is `audit.py` in the same folder. It also rejects undeclared host captures, memory/system/MMIO errors during capture, and unexpected warnings. Existing strict parser default allowance remains.
- First unbounded run did not finish due to UART2 repetition, so it was explicitly stopped and terminal/container termination confirmed. It was excluded from success evidence without a report. First bounded run lacked CPU report due to post-stop JSON .NET byte conversion error and was excluded. Only output was corrected and a new input run afterward. Neither trial was deleted.

Forty-five seconds is an observation ceiling, not a performance or latency measurement. Full SRAM/scheduling equivalence, normal font-bank, integrated display, and physical installation/recovery remain incomplete. Overall product conditions remain 13/29, 44.8%.
