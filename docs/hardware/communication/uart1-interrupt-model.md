# UART1 interrupt wiring

This was under investigation/implementation and is not validation of full boot, screen output, or physical hardware.

IER `0x471` in the three actual main images enables TXCMP (bit 0), RX (4), TX (5), RX timeout (6), and overrun (10). The pinned header assigns UART1 IRQ 16; the wrapper at image vector 32 calls the common handler with module 1. The common handler queries enabled status, clears it, calls the service, and checks RX/timeout/TXCMP bits. Actual source/image hashes and bounded disassembly are in private `uart1-irq-research-01`. Function names reflect semantic comparison with the public HAL; they do not claim original symbol recovery or complete SDK equivalence.

Connecting the existing PL011 IRQ directly would leave a difference: bit 0 is modem RI on PL011. Instead, an adapter owns the Ambiq IER/IES/MIS/IEC boundary and reuses common bits 1–10 from the existing PL011 engine. The existing engine sets TX raw after UART enable and TX write, and clears it through IEC. This is a pinned runtime assumption, not proof of actual FIFO thresholds or transmission timing.

The opt-in `--uart1-interrupts` selects IRQ16 wiring. Without it, nonzero IER remains blocked. DMA interrupt bits 11/12 are rejected. RX/error/modem causes are not generated without real input. Under the existing immediate-TX assumption, TXCMP bit 0 latches when a byte is transmitted and clears at IEC bit 0. The adapter asserts IRQ when raw & enable is nonzero and connects it to NVIC16. RX data supply, timer-based timeout, DMA, a physical serial link, and precise TX completion timing are not implemented.

The alternative of storing IER without asserting IRQ was not adopted because it cannot validate ISR execution. Direct PL011 wiring was also rejected because it hides the vendor bit-0 difference. This wiring is within the approved simulator development scope and does not include actual glasses UART, BLE, USB access, or firmware writes.

## Initial run and clear-all boundary

The initial 66 unit checks and three main runs asserted the IRQ line but recorded zero ISR entries. The next operation was an `IEC=ffffffff` write. The actual stock 2.4 callee writes IEC44 and then reads MIS40; its caller passes `r1=-1`. The public HAL also uses `ffffffff` for clear-all. Therefore, only when IRQ is opted in, this value is normalized to the defined `1fff` cause clear. Arbitrary reserved-bit `2000` writes remain rejected. The non-opt-in boundary is unchanged. This is a model contract limited to observed commands, not validation of actual reserved-bit electrical behavior.

Synthetic M55 guest validation is a separate fixture with power seeded by the host. It checks IRQ16 entry for TX and TXCMP, ISR IPSR32 observation, clearing, and return; it is not used as evidence of actual main boot. For actual main, a hook at the original vector address counts exception entry only when ICSR active is 32. IRQ-line counters alone do not establish ISR execution.

## Final results

The final sources passed 68 unit checks, 14 shared-bank checks, two synthetic CPU IRQ16 checks, and five actual-main conditions. The unit core and combined CPU/shared/main source snapshots were compared against current file hashes. Actual stock 2.4/2.3/Faceclaw recorded 26 UART writes, IER `0x471`, one clear-all, one IRQ assertion, and two transitions, then stopped at `PWRCTRL.DEVPWREN` address `0x40021004 = 0` after setting CR0. Actual main recorded zero ISR entries and zero TX; do not conflate this with synthetic-guest ISR success.

Without the IRQ option, the existing IER `0x471` is blocked. The stuck-off case has zero UART configuration writes, one power block, and no IRQ. Missing CLI dependencies are rejected before reading inputs or creating output. The next step is lifecycle research covering UART power-off, state retention, and resumption. CFW differences excluding vendor-version differences and synthetic input limitations are recorded in `raw-firmware-execution-audit.md`.

Evidence: private `uart1-irq-verification-01/final-verification.json`. The independent review used a fallback from the same GPT-6 family and had no separate transcript archive. No additional critical defects were found. Full boot, display, installation readiness, and physical UART validation remain incomplete.
