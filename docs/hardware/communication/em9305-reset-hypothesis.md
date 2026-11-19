# EM9305 reset/ready hypothesis and first SPI configuration boundary

Follow-up to bw-0242. Without physical glasses access, original ARM main reset was connected through GPIO93 reset output, GPIO117 ready input, and first SPI configuration. **This does not reproduce actual EM9305 timing or normal communication.** This unit is deferred with SPI transfer not reached. The next priority is investigating the W5 damaged-main recovery actor.

## Boundary between confirmed original behavior and assumptions

Stock 2.4 GPIO117 consumption PCs are low wait 0x501bf2, high wait 0x501c1a, and SPI header precheck 0x50190c. Stock 2.3/Faceclaw are 0x54a54a, 0x54a572, and 0x54a264 respectively. All three pinned originals extract only bit 21 immediately after reading. Low/high waits use R6 and header precheck R8 to point to GPIO word 0x40010410. Root address and PAD117 0x400101d4 must also match.

The original holds GPIO93 low, raises it high, then waits for GPIO117 low→high. Each loop uses counter 0x7530 and failure returns 4/5 respectively. The delay wrapper's factor of 1000 was confirmed in original instructions, but actual time calibration was not verified. Manufacturer reset/RDY body text has not been obtained.

`BlackwallEm9305ResetHypothesis` separates this **host-expected procedure** from the following **unmeasured fixture**:

- Minimum reset pulse 1 µs, busy-low 10 µs after release, ready-high 1000 µs. Delay control is 5000 µs. These are not actual chip timing specifications.
- High impedance immediately after release is interpreted high only with actual stored pull-up config 0x2093. With pull-free 0x93, only driven state is provided.
- State is determined by accepted configured GPIO93 writes and Renode virtual time, not read count. Other GPIO, PC, and register contexts are rejected by existing guards.
- Word padding is provided only at the original three bit-21 consumption points. The full GPIO word and general CQ input are not implemented. If CQ later needs the same pin, share the state owner instead of duplicating it as a separate constant.
- Configured low no-op is also delivered as reset assert, but unconfigured idempotent writes are not treated as actual output events. Events occur after full mask validation and latch commit.
- Default profile is off. Opcode, branches, returns, and runtime PC are unchanged. Time synchronization and synthetic input themselves can affect branching and timing.

## Original main execution results

| Input/condition | Actual observation | Next stop |
| --- | --- | --- |
| Stock 2.4 nominal | Three reset writes, 62 inputs, reached header precheck | 0x58253a, DCXCTRL 0x40056124←0x10 |
| Stock 2.3 / Faceclaw nominal | Same reset procedure and 62 inputs | 0x57b1e2, same DCX configuration |
| Stock 2.4 delayed | Ready after 287 inputs, reached same header/SPI configuration | Same boundary as nominal |
| Stock 2.4 never-low | After 30,001 first low-wait attempts entered another input-consumption path | GPIO117 read at 0x501676; context unsupported |
| Stock 2.4 never-ready | 30,003 inputs, reset writes increased to 5, observing additional original reset path | GPIO117 read at 0x502000; context unsupported |
| Stock 2.4 model-off control | No reset model; previous observations, CPU, instruction count, and boundary exact | Previous GPIO117 read at 0x501bf2 |

UART0 bytes 289/285/285, IRQ 8, and existing event prefix were preserved. Global CQ input is -1 (unknown), SPI commands/CQ pairs 0, and no peer exists. No extra input was fabricated to pass subsequent failure-condition paths. Attempts after error return were not proved safe fallback or recovery. The never-ready final phase is released because of an additional reset, not ready success.

## SPI boundary and preserved failures

In the first exploration, the existing Apollo4-based IOM backend passed DCXEN bit 4 as an unhandled warning and later stopped setting MSPICFG bit 2. The common runner rejected this warning, so it was not used as a passing run.

The pinned Apollo510 header's DCXCTRL description says bit 4 enables DCX output generation during SPI offset transmission. To avoid storing it while appearing to implement the external signal, nonzero DCXCTRL was rejected **before writing** as `spi-dcx-unsupported` in the opt-in SPI configuration path. Default I2C path and source-reset 0 writes remain. This unit was not extended by implementing more SPI configuration latches or peer responses. Header candidates prepared by the original are 0x81/0x00, but actual SPI transfer did not start.

Thus bw242's original deliverable of complete IOM6 initialization and first transfer remains incomplete. Work is recorded as deferred; S6, D3, W5 completion criteria and 13/29 progress are not increased.

## Verification material

Red tests confirmed missing new class and failure to reject DCX respectively. Final verification covered 50 native unit checks, matching existing GPIO 29/IOM6 66 results, original main nominal 3/control 1/delayed 1, and two failure conditions. Raw nominal-contract false results for failures were retained and a separate audit written after source confirmation. Native was not rerun for the audit. A GPIO marker typo in the regression collector was resolved by reinterpreting saved logs without rerunning the same test.

Final saved audit 111 checks and common-contract unit 13 passed. These verify a limited hypothesis model, not physical hardware. Private `simulator/em9305-reset-verification-01/audit.py` and `report.json` preserve source hashes, original opcode consumption points, logs, manifest, contract, and controls. Inputs, failed trials, model, and raw logs are separated in `em9305-reset-*` folders. Execution Docker processes exited.

Follow-up bw268: [original main display/SPI integration boundary](../../firmware/main-display-integration-frontier.md). It stops at SPICFG=4 after the DCX no-pin latch, with SPI commands=0. Actual wait conditions of UI/two display workers were confirmed; message/notification producers are the next analysis target.
