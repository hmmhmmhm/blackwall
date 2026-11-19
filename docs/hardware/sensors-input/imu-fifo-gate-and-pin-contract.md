# IMU initialization gate and GPIO38 callback

bw464. The producer of the [FIFO upper consumer function](imu-fifo-read-transport-contract.md)'s gate was found. **The gate becomes 1 when the mode initialization wrapper returns; it is not IRQ pending.** A separate timestamp/event callback is registered on GPIO38. Normal GAF, actual IRQ input, and natural sensor consumption remain incomplete; overall 10/16=62.5%.

## Initialization completion versus success

| Item | Stock 2.4 | Stock 2.3/Faceclaw |
| --- | --- | --- |
| Mode command handler | 0x4c6198 | 0x4baadc |
| Initialization wrapper | 0x4c3210 | 0x4b7b54 |
| Gate slot | 0x200774f4 | 0x20077d00 |
| Timestamp slot | 0x200774f0 | 0x20077cfc |

If mode at message+4 is less than 5, the command handler executes gate 0 → call initialization wrapper → gate 1. It does not use the wrapper return value as a success condition for the gate write. Earlier [initialization wrapper analysis](imu-startup-ui-dependency-audit.md) also identified a path that does not check lower-level errors. Thus gate 1 must not be treated as normal sensor readiness or successful GAF computation.

For each of three originals, 15 conditions (modes 0–4 × wrapper ABI returns 0/-3/-1) and two conditions (modes 5/255) were executed. The actual command handler wrote the gate; the host did not. Gate 0 and passed mode were checked at wrapper entry. Valid modes set gate 1 regardless of return, while rejected modes retained the existing 0. SRAM outside the expected gate was preserved. Logging query and wrapper are explicit leaf ABIs, not actual initialization.

The existing natural main waiting/stopping at GAF service is separate from this command handler return boundary. The test's ABI returns did not let actual main pass or create evidence of normal initialization.

## GPIO registration and callback

| Item | Stock 2.4 | Stock 2.3/Faceclaw |
| --- | --- | --- |
| pin38 callback | 0x4c615e | 0x4baaa2 |
| bank1 IRQ57 ISR | 0x4fc90e | 0x557536 |

The `pin38 / config word 0x20002 / callback Thumb pointer` record in original flash was compared with slot 38 of the existing GPIO registration pointer table. The callback is already registered in saved SRAM. IRQ57 entry in the vector table and IRQ number 57 in the flash context read by the ISR were also compared. Pin 38 is bank 1 bit 6.

Packed config word 0x20002 alone does not establish actual PINCFG38, edge polarity, idle level, or enable state. Actual pad configuration and enable mask must be checked in the next native connection. Physical wiring, voltage, and IRQ timing are unknown.

The callback returns immediately at gate 0. At gate 1 it calls a separate predicate helper; if the helper returns 0, it proceeds through tick getter → timestamp slot write → message type 2 construction → producer call. The predicate's full meaning was not established in this scope.

One gate-0 control per original used saved state unchanged and did not enter predicate/tick/producer. Then three callback conditions ran in CPU state where the mode handler actually wrote gate 1: predicate 0/tick 0x12345678, predicate 1/no tick call, and predicate 0/tick ffffffff. Timestamp, message type 2, source gate preservation, and other SRAM preservation were checked. Predicate/tick/producer were isolated as leaf ABIs; this is not actual queue/task consumption or actual ISR/NVIC execution. The host did not write gate 1.

The final 63 runs comprise 51 mode, three gate-off, and nine timestamp callback runs. Test counts are not added to acceptance progress.

## Next connection

Before adding a GPIO38 input model, pin original PINCFG38/enable and IRQ57 wiring. Preserve the boundary that input does not lead to sample processing in the initially closed gate state. Do not write the gate from the host or manipulate GAF ready to open it. Verify actual pin edge→ISR→registered callback separately from FIFO bus/task consumption after normal initialization.

Evidence is outside Git at `simulator/imu-fifo-gate-contract-01/{probe.py,report.json,manifest.json}`. The pinned bundle's main and saved snapshot were used, and the pointer-table address from the existing GPIO27 source contract was reused to read the actual pin38 value. No original firmware or peripheral model changes, physical access, subagents, or external publication.
