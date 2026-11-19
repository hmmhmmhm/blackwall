# CS/RDY and original Active State Entered event acceptance

Task bw-0273 connected logical CS and header/payload phases according to the [framing contract](em9305-hci-framing-contract.md), confirming the path where stock 2.4, stock 2.3, and Faceclaw 38 original M55 mains accept virtual `04 ff 01 01`. This does not verify actual controller state, BLE connection, or integrated main boot. No device was accessed.

## Implemented contract

Optional `BlackwallEm9305EventPeer` supplies only one fixed four-byte event. Event content is an explicit constructor input: normal test `04ff0101`, control `04ff0103`. It observes pin 149 output events and queues the event only when the existing reset hypothesis judges a qualified release. Output callback occurs after latch change and is not used as a pre-write veto.

States are Unreleased → Queued → HeaderActive → PayloadReady → PayloadActive → AwaitRelease → Consumed. Header/payload begin only with known-low CS. Header `81 00` returns `c0 04`. IOM completion of the header only moves to PayloadReady and does not end the CS frame. After the original reads four bytes via RX-only SPI, actual virtual GPIO149 high must arrive to complete the frame. Incomplete header, CS interruption, or partial-payload interruption is not counted as success.

RDY is separated from the existing reset timing hypothesis. Original fall/rise consumption points use the existing reset hypothesis. At pinned original consumers for initial data-ready, post-header buffer-ready, and idle after CS release, peer phase and CS state are checked together. Unsupported PC/context/configuration and indeterminate states are blocked. High was not supplied to a new PC independent of CS and phase. Actual payload-ready time transitions remain unimplemented in this explicit untimed scenario.

The SPI word engine adds RX-only READ solely for an explicitly specified `IBlackwallReceiveSpiPeer`. After checking length, format, and phase it clocks with dummy MOSI and puts received words in FIFO. READ is not enabled for the existing scripted write peer. Offset/CONT/other CE, flow control, over 32 bytes, and actual controller firmware remain unsupported.

Controller reset alone does not requeue an already consumed event. Qualified release under the separate EM hardware-reset hypothesis can start a new initial-event scenario. This is an explicit simulation state model, not verification of actual device link-layer/NVM state.

## Retention limit in HCI cleanup

After reading the first event, original HCI read performs IOM cleanup before returning. Stock 2.4 `0x50178e` calls original IOM disable/save and stores CQFLAGS in the same retention block `0x581e82` as before. The default one-read profile blocked the second call.

Default `cqStartupRetentionBudget` remains 1; only an explicit profile with pinned retention PC can select 2. Existing clock/SPI/CQ/CPU R1/handle/module conditions and global unknown input remain. Power-down does not automatically replenish budget. The basis for using the same retention-only representative value a second time is the [existing save/restore contract](../power/iom6-retention-copy-contract.md)'s 768 ARM blocks and 2696 conditions. This task rechecked and reused that report and all source pin hashes. It is not expanded to actual pin values or whole-function equivalence.

## Results from original reset main

| Input | Virtual event | Original success log | Original RF error byte | Next strict boundary |
| --- | --- | --- | ---: | --- |
| Stock 2.4 | `04ff0101` | `Enter active state` present | 0 | HCI write RDY `0x501676` |
| Stock 2.3 | Same normal event | Present | 0 | Same consumer `0x549fce` |
| Faceclaw 38 | Same normal event | Present | 0 | `0x549fce` |
| Stock 2.4 control | `04ff0103` | Absent | 5 | Recovery/reset branch RDY `0x502000` |

In all three normal cases the original received header and payload; peer header/payload/frame completions were one each. Original code, PC, branches, and returns were unchanged, and event comparison was not performed on its behalf. New observers did not collect IRQ timing or a full PC trace.

Acceptance evidence did not rely solely on the peer's own completion flag. String location/call in the original success branch was confirmed and the success string found in actual UART adapter transmit bytes. The actual original RF error byte address was also found from a ROM literal and 0/5 compared in full native SRAM exports. Stock 2.4 error byte address is `0x20077bee`. Changing only the event's last byte 01→03 under the same environment changed the original result.

IOM cleanup/reset after payload resets the word engine's current Completed/BytesExchanged/LastReceiveWord to 0; this is not interpreted as transfer failure. Cumulative peer transaction/frame history, success log, and actual RF state were used together. For the same reason, the old stack address of the initial event buffer was later reused and is not claimed to still hold the event.

The original treated the wrong event as an error and entered recovery/reset. Peer state also became Queued after a new qualified reset. It stopped at an unsupported RDY consumer in that path; later recovery is not considered successful. Both normal and error boundaries block a read of `0x40010410`.

Default-option control exactly matches previous positive-header-only CPU, instruction count, existing observations, and boundary. The new profile and retention budget did not silently widen the default path.

## Verification scope and failure history

Native unit/regression passed 190 conditions: new event/frame 19, reset hypothesis 48, SPI word 50, preflight 21, DCX 21, existing IOM6 31. New-feature red failed due to missing peer type. Units test configured peripheral APIs and are distinct from original main results.

Preserved outside Git in `~/Library/Application Support/Blackwall/simulator/`:

- `em9305-event-research-01`: previous two models and unit builder/input.
- `em9305-event-red-01`: missing-type failure before implementation.
- `em9305-event-unit-01`: test input omitted GPIO config unlock and was blocked by guard. Correct configuration procedure fixed the test without removing protection.
- `em9305-event-unit-02`: test incorrectly expected payload counter accumulated across reset to be 0. Corrected to compare cumulative meaning and abort increment.
- `em9305-event-unit-03`: first 18 conditions passed. `-04`: 19 passed including final model and explicit budget.
- `em9305-event-*-regression-01`: regressions for the five existing areas above; all report file hashes also rechecked.
- `em9305-active-event-main-01/stock24`: after event transaction, inherited previous diagnostic could not find new peer `Transmitted`, preventing final CPU report. A compatible diagnostic property returning actual transmission history was added.
- `em9305-active-event-main-02/stock24`: first transaction/frame completed but stopped at second retention save during original HCI cleanup. Not yet reported as successful event comparison.
- `em9305-active-event-main-03/{stock24,stock23,cfw}`: three final normal-event captures. Stock24's first plan/report with failed next-boundary prediction remains unchanged.
- `em9305-wrong-event-main-01/stock24`: initial prediction retained as semantic failure because actual recovery boundary differed from normal write boundary.
- `em9305-active-event-control-01/stock24`: exact default-profile control.
- `em9305-active-event-saved-audit-01`: audited five final captures against reviewed boundary contracts. It checks that execution-plan items other than semantics were unchanged, without overwriting initial failures or rerunning native.
- `em9305-active-event-contract-01`: native original log/RAM acceptance and rejection analysis.
- `em9305-active-event-verification-01`: pins analyzer and 16 local dependencies; verifies final source model/plan, unit, audit, and existing retention-proof hashes.
- `em9305-active-event-contract-02`: reanalysis of pinned copy, byte-identical to initial report.

Seven native attempts total include two development runs; five are final verification captures. All ran sequentially with terminal results checked. Native was not rerun for saved audits. Proprietary images and virtual RAM remain outside Git.

Code: `tools/renode-iom.cs`, `tools/renode-em9305-reset.cs`. Three JSON execution plans cover normal, peer-version, and wrong event, explicitly pinning source address differences. Analyzer: `tools/inspect_em9305_active_event.py`.

## Remaining scope

This result means **the original host naturally accepted/rejected an explicit virtual controller initial event**. It is not success of actual EM9305 secondary firmware execution, silicon timing, physical CS wiring, physical BLE, complete main boot, or display.

Next identify the first `42 00` HCI write header and packet the original intends to send, then add a limited-state model for write-ready and buffer capacity after CS assert, and command/event response. Consumed-event idle data-ready and readiness for a new write transaction must not be treated as equivalent. Do not unconditionally open unsupported write consumption by returning high. Display notification/redraw producers, normal font-bank, and web installation/recovery integration also remain separate.

Overall product completion remains scope v2 13/29, 44.8%. There was no physical connection, flash, OTA, or persistent memory change.

Follow-up bw274: [first HCI command contract](em9305-first-write-command.md). The first packet intended for transmission is `fd01`, an eight-byte read at address `00f04b88`. Actual response remains unknown and affects the trim-update branch. Existing RAM/source and ARM fragments were analyzed without native restart or physical access.
