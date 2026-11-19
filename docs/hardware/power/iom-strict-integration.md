# IOM2 Strict Integration Verification

> bw-0117 interpretation correction: MI2CRST bit 6 is explicitly “Not used” in pinned Apollo510 header/SVD. The historical software-reset-request interpretation below was inaccurate; the stop at that time was the model rejecting bit 6. It is distinct from actual SMOD_EN reset.

Work bw-0115 was performed on a Renode virtual board without physical connection, flash, or OTA. Original main runs without function replacement or forced PC branches.

## Change scope

- Reuse existing UART digital power-state transitions through `BlackwallPeripheralPower` and connect IOM2 mask 8 to shared DEVPWREN/STATUS bank. Only one domain changes at a time.
- Separate only IOM2 `0x40052000..0x400523ff` from existing strict guard. Guards before/after reference the same low-bank owner. IRQ connects to NVIC8.
- Place Apollo510 register masks, clock/FIFO/type differences, and power/width/unsupported-function checks before the existing pinned Renode Apollo4 polling engine. Structural and numeric sources are `iom-platform-research.md`.
- Block access before power-on, unregistered offsets/widths, SPI transactions, unregistered I²C peers, nonzero DMA/CQ, I²C soft reset and LSB, and new CMD during progress. No synthetic peer is connected to actual main.
- Idle/FIFO state is a functional-model assumption. Physical clock, bus timing, and power delay are unimplemented. DMA/CQ have only disabled-zero responses. Writing 0 is a no-op initialization, not actual execution.
- UART IRQ-hook loop variable `vector` overwrote report reset address; it was separated as `irq_vector`. Existing CPU startup setting `VectorTableOffset 0x438000` was unaffected. Historical frozen reports were not modified; new reports compare directly with original vector.

## Newly discovered existing-engine defect

In synthetic eight-byte TX, preparing four bytes first and FIFOPUSHing the remaining four during execution transmitted zeros in the latter part. `BLACKWALL_PARTIAL` in `private:simulator/iom-strict-unit-07/renode.log` preserves the observation differing from request. Pinned engine `Fifo.Push` starts transmission via Count-increment callback before storing the new value in memory. This order is consistent with reproduction.

The current adapter stops before starting a command if TX length exceeds bytes already prepared in FIFO. This does not implement streaming TX. Fixing the defect and reverifying streaming are required follow-up, not completion of full IOM/integrated main.

## Current original main results

Initial stock 2.4 `private:simulator/iom-strict-main-stock24-01` executed original instructions from reset 0x5fbe3f, powered on IOM2, and progressed to configuration initialization. At PC 0x582062 it attempted 0x3f270 write to MI2CCFG (0x400522c0) and stopped because MI2CRST bit 6 was unsupported. Commands=0; this is not successful actual I²C transfer or sensor discovery.

In final same-source comparison `private:simulator/iom-strict-main-comparison-01`, stock 2.4 at PC 0x582062 and stock 2.3/Faceclaw38 at PC 0x57ad0a requested the same write `0x400522c0=0x3f270`. Power on 8, writes 1, commands 0; boot/display remain incomplete. Same endpoint is not evidence of identical complete instruction traces or patch execution.

Under stuck-off, stock 2.4 attempted 0x1010 to FIFOTHR (0x40052104) at PC 0x581fa2. With power status 0/phase stuck-off, adapter blocked before transfer; writes 0/commands 0. This shows original code attempted configuration after power readiness failure, not safe fallback or physical-device safety.

## Verification record

- After power-code extraction, UART adapter 117 and existing shared-bank 28 conditions passed: `private:simulator/iom-power-uart-regression-01`, `iom-power-shared-regression-01`.
- IOM first test 01 failed compilation due to using placement in combined C#; 02 failed named-path lookup of unmapped power. After corrections, independent 68 conditions in 03/04 passed.
- Streaming TX test 05 added after review failed on actual transmitted-byte mismatch. 06 failed .NET byte JSON serialization of observations; 07 captured zero transmission. These are not treated as success.

Synthetic power/register initialization/FIFO/IRQ tests are distinct from actual main results. Physical verification, full boot, integrated display, and installability assessment remain absent. Product progress is 13/29.

- Strengthened `iom-strict-unit-08` 75 conditions include streaming rejection, long RX36 FIFO refill/byte accuracy, active CMD overlap rejection, and busy-off rejection. unit09 passed 76 conditions adding FIFO/CMD preservation on rejection.
- `iom-strict-shared-01` 18 conditions check single shared-bank change, preservation of other domains, one off callback, cancellation, and actual SysBus boundary blocking before/after.
- `iom-strict-mask-audit-01.json` confirms adapter's 36 masks match pinned SVD/header. Initial audit regex read only 30 because decimal returns were excluded; inspector was fixed. Model masks were unchanged.

## Final artifact review

`tools/verify_iom_evidence.py` compared execution sources, frozen C#, host source, original main SHA, reset vector, UART regression state, power-failure guard, and stock 2.3/CFW script differences. They are preserved in `private:simulator/iom-strict-verification-01/report.json` and 15 source copies. Independent same-GPT-6-family review found no additional significant issue. Other-family review and archived transcript comparison were not performed. Streaming TX engine fix, I²C reset semantics, actual peer identification, actual main bus transfers, and full boot/display remain follow-up tasks. No physical-device access occurred.
