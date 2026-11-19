# Original HCI initial event and header/payload framing

Task bw-0272 checked the host contract needed after the [first one-shot SPI transaction](../power/iom6-spi-word-transaction.md). Model code and original images were unchanged. Manufacturer material, static source, M7 fragments, and M55 reset-main evidence are distinguished. No physical device access occurred.

## Initial event actually expected

| Role | Stock 2.4 | Stock 2.3 / Faceclaw 38 |
| --- | --- | --- |
| Controller initialization function | `0x501ba0` | `0x54a4f8` |
| HCI read function | `0x5018d6` | `0x54a22e` |
| Header full-duplex HAL | `0x5823fc` | `0x57b0a4` |
| Payload RX HAL | `0x5820d8` | `0x57ad80` |
| Post-header RDY read | `0x501a30` | `0x54a388` |

After successful HCI read, each original initialization function compares the first four bytes of the received buffer with ROM `04 ff 01 01`. Signature uniqueness, initialization→same reader call, ROM pointer, and length-4 comparison call were checked in source. This is what the original host expects, not evidence that the actual controller currently sends the event.

Indexed text of the manufacturer's [EM9305 datasheet §11.3.1](https://www.emmicroelectronic.com/sites/default/files/products/datasheets/EM9305-DS.pdf) describes Active State Entered event code `ff`, subevent `01`, matching the original constant. Distinguish Configuration Mode Entered subevent `03`. Controller NVM/link-layer state and actual device boot outcome remain unconfirmed.

Direct PDF opening redirected to a Swatch Group company page. Search-indexed text for the manufacturer URL indicated v4.5.3 (2025-08-20), but no local PDF hash or visual review was obtained. Do not claim direct verification of the latest PDF merely because the URL is official. Original-image constant/function verification is independent of this access limitation.

## Frame structure confirmed in source

The original GPIO helper's pin 149 low call writes mask `0x200000` to bank 4 of GPIO clear base `0x40010458`; high writes the same bank/mask at set base `0x4001043c`. Actual addresses are `0x40010468` and `0x4001044c` respectively. GPIO input reads bit 21, pin 117, of `0x40010410`.

The successful source path is pin 149 low → `81 00` two-byte full-duplex header → status/length check → post-header RDY recheck → payload read via separate RX HAL → pin 149 high. The source payload descriptor uses RX direction 1 and the header's available length. Stock 2.4 payload HAL call is `0x501a92`. For event length 4, the next SPI READ's expected CMD is `0x402`, but this native run stopped before that request.

Indexed v4.5.1 text of [manufacturer SPI slave §8.8](https://www.emmicroelectronic.com/sites/default/files/products/datasheets/9305-DS.pdf) also describes header/payload within the CSN-active interval and phase-dependent RDY meaning. Do not confuse it with EM9305 **SPI master** §8.7. Physical connection of pin 149 to EM9305 CSN on the G2 board is unverified; treat it as a logical CS candidate supported by source and protocol.

## Original retry fragment verification

Three images × six status/length combinations × retry indices 0/9 = 36 cases ran on M7. `c0/4`, `c0/1`, and `c0/ff` proceed to the nonzero-length acceptance boundary. `c0/0`, `00/4`, and `80/4` call the actual original GPIO helper, perform the store corresponding to pin 149 high, and increment the counter. Index 0 reaches the next assert boundary; index 9 reaches counter 10 and the header-error boundary. The source limit comparison is also 10.

This did not execute all ten header transactions end to end. Fragment entry, stack, and counter were explicitly supplied and execution stopped at the next semantic boundary. Internal branches and the GPIO callee were not bypassed. GPIO MMIO captured a plain memory store, not simulated latch, voltage, interrupt, or RDY timing. No memory-write hook was used. Actual GPIO helper entry counts were checked against paths.

## Original M55 main with positive header

This explicit test used the same binary as the existing model, changing only peer response `c0 00` to `c0 04`. No four-byte event body was supplied.

All three native mains received the header and stored `c0 04 00 00` on the original stack. Original R9 was parsed length 4 and R4 HAL success 0. IOM logical transaction completion callback=1, words remaining=0, SPI configuration=0, yet **pin 149 output remained low**. The next GPIO117 read then strictly stopped.

This specifically shows IOM `FinishTransmission` must not be treated as HCI CSN rising. It is virtual output-latch state, not physical CS measurement. The actual electrical relationship between SPI bus CE0 and GPIO149 is also unknown.

A stop at payload READ CMD was initially predicted, but execution actually stopped earlier at the post-header RDY consumer. Existing `BlackwallEm9305ResetHypothesis` supports reset fall/rise and the RDY consumer before the first header only, rejecting the new PC. This confirms a reset-only model cannot substitute for protocol buffer-ready phase. Do not confuse source-predicted READ `0x402` with a request actually executed natively.

## Preservation and reverification

Tools: `tools/inspect_em9305_hci_framing.py`, `tools/inspect_em9305_post_header.py`, `tools/em9305-hci-payload-boundary-candidate.json`.

Outside Git, `~/Library/Application Support/Blackwall/simulator/`:

- `em9305-hci-reference-01/sources.json`: manufacturer index/direct-access limitations and fact classification.
- `em9305-hci-framing-01`: failed copy and record from source-offset error in inspector. Check positions for pin argument and descriptor mov were corrected.
- `em9305-hci-framing-02`: first 36 fragments passed. `-03`: final pass with actual GPIO helper trace-count comparison added.
- `em9305-hci-payload-boundary-main-01/stock24`: preserved original plan/report with **semantic failure due to incorrect CMD boundary prediction** in the first native run. Execution and header exchange completed.
- Same root `stock23`, `cfw`: ran after precontract corrected to actual RDY boundary; execution/semantic passed.
- `em9305-hci-payload-boundary-audit-01`: audited three saved runs against actual RDY boundary contract. Initial stock24 failure was not overwritten; auditor confirmed no execution-plan items other than semantics changed. No native rerun.
- `em9305-post-header-contract-01`: analysis of actual native buffer, registers, logical CS, and RDY guard.
- `em9305-hci-framing-verification-01`: pinned source inspector and 16 dependencies, two report hashes, model invariance, and manifest referencing prior verification.
- `em9305-hci-framing-04`, `em9305-post-header-contract-02`: reanalysis with pinned dependencies, byte-identical to each respective initial final report.

Model hash matched bw271 final verification and existing 123-condition/off-control evidence was reused. The same unit/native controls were not rerun without code changes. Only three new native runs had different header input, and each terminal result was checked sequentially.

## Conditions for the next model

The next unit must bind **logical CS assert → header exchange → buffer-ready RDY → RX payload → CS release** state. Existing GPIO output events can connect source pin 149 behavior, but the output callback occurs after latch change and must not be used as a pre-write veto. Do not extend by unconditionally returning RDY high at a new PC.

Then test `04 ff 01 01`, supported by source and manufacturer material, as an explicit virtual event and distinguish empty/invalid status/event, busy, and interruption scenarios. Do not claim identity with actual controller state; offsets, GPIO/RDY timing, payloads over 32 bytes, and actual BLE stack require separate verification.

Normal full main startup, integrated display, web installation/independent recovery, and physical verification remain incomplete. Overall product completion remains scope v2 13/29, 44.8%.

Follow-up bw273: [virtual active event delivery](em9305-active-event-transport.md). CS/RDY phases and RX-only were connected, confirming initial event acceptance and wrong-event rejection in the three originals. Optional budget 2 was added for the same retention cleanup; default 1 and unknown global inputs remain. Full main/BLE/display/physical work is incomplete.
