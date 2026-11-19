# Natural double-click application start and short UART reply

bw446. **Stock 2.4 original main reset → actual virtual touch double-click → original app 1 start request → UART transmit/peer reply → original UI dispatch and registered callback entry** was connected. No test caller invoked the app producer and PC/TCB/readiness were unchanged.

App 1 callback return, render, and pixel output remain unverified. E09/E11 are partial; overall **10/16=62.5%** and API screen 3/6 remain.

## From actual input to app request

The [idle-scroll discard](touch-family-app-and-idle-routing.md) control was reused with frame changed to `020800003412cdab0180ffff5ac317e9`. Original code interpreted flags 08 as code 1 and dispatched role 1/code 1/packed 0. The actual schedule manager double-click branch, app 1 producer call `[1,0,0,0]`, and R0=0 return to original caller were confirmed.

The original generated schedule packet `0201010000000000`. The original UART task subsequently allocated request ID `0x800d`, channel 2, content length 8 bytes. Actual DMA frame:

`01800d00080002c2220201010000000000c890`

Original start/chunk/finish, descriptor, ID, packet, and return to the same UART task/stack were checked. The host did not write nodes or reply records.

The virtual peer's normal reply is `01800d00010000017302c181`. Original peer listener/encoder ran in isolated ARM and confirmed channel 0/status 2 replies to command header `0x0102` for two IDs. This standalone test uses synthetic descriptor/caller; it does not mean full boot of the other temple or physical display completion. Only bytes in this format were injected into UART FIFO during main execution.

## Actual UART gap discovered

In the existing model the 12-byte reply remained in FIFO. Native RX threshold was 16 bytes, so no IRQ occurred and it did not reach the source parser. Replies were not duplicated or padded with another packet to cross threshold.

Default-off `receiveTimeout` was added to `BlackwallUartAdapter`. This optional contract requires UART0, interrupts, and receiveFifo all enabled. If FIFO remains nonempty for 32 bit-times after last reception, it sets RT raw bit 6; the mask determines IRQ. FIFO drain, reset, and powerdown clear timer and RT. New reception restarts counting. [ARM PL011 TRM §2.8.4](https://documentation-service.arm.com/static/5e8e36c2fd977155116a90b5?token=) and [Ambiq Apollo/Apollo2 description](https://support.ambiq.com/hc/en-us/articles/360000193652-Q-A-Apollo-and-Apollo2-UART-Receive-Interrupts) were consulted and compared with RTIM/RTRIS/RTMIS/RTIC bit 6 in pinned Apollo510 SVD.

Under the adapter's existing nominal 24 MHz/clock select 1 contract, limit is `8 × (64×IBRD+FBRD)` clock cycles. Native divisor 104 gives 832 cycles and reported baud 923076. These are not measured physical Apollo510B clock/serial timing. Virtual burst input has no wire inter-byte time.

The model also explicitly starts a new 32-bit interval after RT clear with bytes pending. This recurrence detail has not been physically verified. Baud/clock changes while buffered are rejected; receiver disable preserves bytes and stops counting. No claim is made to implement timeout for error frames, overrun, or other clock sources.

## Actual timeout IRQ and natural UI

The timeout profile read a single 12-byte reply. At IRQ entry, raw `0x61`, masked `0x40`, pending 12, RT latch 1, and actual exception 31 were observed. Original handler drained it; total UART reception was initial replies 24 + display reply 12 = 36 bytes, returning pending/RT to 0. Guest registers were exact before/after reply injection.

Original master reply called `0x469608 → 0x445e74`. The first observer incorrectly specified producer `0x445f74` and did not stop at the intended point. It was corrected against source BL and the prototype preserved.

| Point | Actual observation |
| --- | --- |
| UI producer | app 1, original content pointer, length 0 |
| UI dispatch `0x4456e8` | app 1/type 2/staging/length 0 |
| Actual registry callback `0x4b7a58` | type 2/staging/length 0/original context |
| Consumer task | original `ui_task`, Thread mode, original stack range |
| UI state / display mode | 1 each |
| Callback return to caller | Not observed |
| Pixels/full screen | Unverified |

This path differs from the synthetic app-start caller in the existing API diagnosis. After main reset the original initiated it using only device input and peer reply. UART/peripheral profiles are declared virtual models, not physical behavior certification.

## Observation after callback

With no callback return within 100 ms, current task, live ITCM, and registers were additionally collected. Higher-priority original display driver entered PC `0x40`. Live code is the finite HAL delay loop `subs r0,#1; bne 0x40; bx lr`. Eight executed bytes match original image `0x7bf54f`, and original `0x495ed2` directly called that address. Entry counter was 809. Initial ITCM poison was not confused with live code. This does not establish provenance of the entire adjacent copy helper.

Without changing original, clock, or peripherals, only the callback observation limit was extended once to 1000 ms. Afterwards `ui_task` was executing at original memset wrapper return point `0x457bb4`, and callback still had not returned. Active linked task graph was checked with existing audit helper. Reaching the time limit is not concluded to be an error or infinite loop, and further limit variations are not repeated. Next trace actual calls, allocation, and drawing progress of this initialization.

## Verification and preservation

- Six actual new original M55 runs: app request, existing short-RX gap, timeout/UI-entry prototype, callback observation, live low-address provenance, and one 1000 ms follow-up observation.
- All had CFSR/HFSR, memory violations, and strict guards 0. Failure to reach a planned observer terminal was not counted as completion.
- Two standalone original peer-encoder ARM runs. New timeout 49, existing RX 32, and existing UART/power 117 unit checks passed. Native/unit image digest is the same pinned 1.17 image.
- Unit red lacked the new option. First green attempt was strictly rejected because clock source changed simultaneously with disable. The check and failure were preserved, distinguishing disable with clock preserved from separate rejection of clock change.
- Existing default-off path was tested with RX/UART units. Native initial IRQ execution with timeout on is not claimed exact against off.
- Public changes are the UART adapter block and `tools/verify_uart_rx_timeout.py`. Component bytes outside the adapter were confirmed identical to prior snapshot. Proprietary main/dumps are outside Git.
- Contracts, observer, builder, source/provenance, verifier, and captures in private `touch-idle-wake-research-01` are pinned by `touch-idle-wake-manifest.json`. All owned processes were cleaned up.

No physical access, flash, subagents, or external publication. Normal GAF computation, wake integration across three originals, gesture/ring list, and full-screen acceptance criteria remain.
