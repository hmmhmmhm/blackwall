# IOM6 CMD-before-FIFO Full-Duplex Test Transaction

Work bw-0271. Beyond the storage-only boundary of the [first SPI request contract](iom6-first-spi-command.md), this confirmed the first actual simulated SPI byte exchange and original RX buffer update in main. Stock 2.4, 2.3, and Faceclaw 38 all ran original ARM from reset without changing PC, branches, returns, or original images. No physical device was connected.

## Implementation scope

`BlackwallSpiWordTransfer` is used only when optional `spiWordPeer` is supplied to existing `BlackwallStrictIom`. Explicit IOM6 SPI storage, DCX no-pin, and full-duplex profiles are all required. Without a peer, existing preflight blocking remains.

Supported transactions are SPI WRITE=1, full-duplex mode 0/MSB-first, CE0, offset 0 bytes, CONT=0, length 1–32 bytes. CMD is accepted first, then FIFO word supply is awaited. Command status returns WAIT/remaining while waiting and IDLE after completion. Only bytes corresponding to actual TSIZE in FIFO words are passed to the peer. Returned bytes are stored in RX words packed little-endian. Remaining bytes in the final word are zero padding; FIFO availability is reported as four bytes per word. This untimed representation matches the current original driver and is not a silicon timing measurement.

After transfer, command-complete bit is raised in original IOM interrupt state and reflected through the existing IRQ path. Existing INTEN/INTCLR and default I2C engine remain. RX pop consumes actual words; empty FIFO access is rejected. A new CMD is rejected while unread RX remains or a prior transaction is active. Unsupported commands, offsets, CONT, other CE, excessive lengths, configuration, widths, and peer mismatch are blocked before relevant transaction state changes. Pre-filling FIFO before CMD, flow control, DMA, direct FIFO windows, and timing are unsupported.

This does not implement full BLE payload transfers beyond 32 bytes. Expansion requires first confirming host-driver FIFO flow/backpressure and actual framing.

## Explicit one-shot peer

`BlackwallScriptedSpiPeer` is a test peer allowing **one transaction only**, expected `81 00`, response `c0 00`. It does not implement EM9305 firmware or actual controller initial state. The fixed response is a test input of ready header and zero pending bytes, not evidence that actual G2 has this state after reset.

The peer first checks CMD length and valid bytes of the next supplied word. Upper padding is neither compared nor transmitted. If valid bytes are wrong, the entire word is rejected before sending any bytes. The next CMD after completion stops as `spi-peer-script-unavailable`; unattended responses or retry success are not created. `SetScenario`/peer reset are explicit test preparation, unrelated to actual device reset/recovery. Controller reset aborts active transactions and does not automatically replenish peer budget.

`FinishTransmission` verification is an IOM logical-transaction completion callback, not physical CS electrical-signal verification. An original upper caller calls a GPIO function with pin 149. That pin's relationship to CE0 and actual EM9305 CS, and framing between header/payload, remain unconfirmed and must be analyzed before connecting multiple HCI transactions.

## Original M55 main results

| Item | Stock 2.4 / stock 2.3 / Faceclaw 38 |
| --- | --- |
| Accepted CMD / completed transactions | 1 / 1 each |
| Bytes actually delivered to peer | `81 00`, exactly two bytes |
| Peer completion callback | Once |
| Words remaining after RX FIFO handling | 0 |
| Original native stack RX buffer | `c0 00 00 00` |
| Next command | `CMD=0x201`, blocked before transfer because one-shot budget exhausted |

Stop PC is `0x582594` for stock 2.4 and `0x57b23c` for stock 2.3/CFW. The address is unchanged but state differs: previously commands=0 before accepting the first CMD; now commands=1 before the second CMD after the first transaction completed. The original copied the test RX word to its buffer, continued, and made the next request. This does not mean full main boot or BLE initialization completed.

RX evidence did not use only the model's last response. Actual R5 destination and stack bytes from native reports were read to confirm `c0 00 00 00`. Original HAL frame prologue and saved caller BL/return were compared, and source was checked showing the upper caller tests status `0xc0` and the second header byte. That source-check region was not collected as a separate new full PC trace.

Default peer-off control exactly matches prior CPU, instruction count, existing observations, and boundary. Three successful candidates retained the existing observed event prefix. No new execution observer/runtime hook was added. Unit testing the SPI completion IRQ line is distinct from actual M55 IRQ12 handler execution; separate verification of the latter remains absent.

## Verification and failure history

Fifty native unit conditions cover 1/2/3/4/5/8/32-byte transfers, TSIZE padding exclusion, RX byte/word counts, CMD-before-FIFO, rejection of duplicate CMD/invalid configuration/data/width, IRQ/ack, reset abort, and more. Existing preflight 21, DCX 21, and IOM6 31 conditions also passed, 123 total. Units test configured peripheral API and are distinct from original main execution evidence.

Preserved outside Git under `~/Library/Application Support/Blackwall/simulator/`:

- `iom6-spi-word-research-01`: previous IOM model and test builder/input.
- `iom6-spi-word-red-01`: pre-implementation native log failing due to missing scripted peer type.
- `iom6-spi-word-unit-01`: post-implementation test-code failure querying `@ none` peer node, corrected to use the model-owned actual peer reference.
- `iom6-spi-word-unit-02`: first 50-condition pass. `-03`: final model's 50-condition pass including diagnostic counters.
- `iom6-spi-word-preflight-regression-01`, `iom6-spi-word-dcx-regression-01`, `iom6-spi-word-legacy-regression-01`: existing-profile regressions.
- `iom6-spi-word-main-explore-01/stock24`: first stock run passing the predeclared schema 2 prediction. Despite “explore” in its name, it is a passing capture with final model/contract pinned.
- `iom6-spi-word-main-01/{stock23,cfw}` and `iom6-spi-word-control-01/stock24`: remaining native runs, all sequential with terminal results confirmed.
- `iom6-spi-word-saved-audit-01`: execution/semantic audits passed for four saved captures, without native reruns.
- `iom6-spi-word-contract-01`: actual original RX buffer and source-frame analysis.
- `iom6-spi-word-verification-01`: inspector and six local dependencies, native audit/unit file hashes, current model/plan hash manifest.
- `iom6-spi-word-contract-02`: reanalysis with pinned dependencies, byte-identical to the first report.

Code is `tools/renode-iom.cs`, execution plan `tools/iom6-spi-word-candidate.json`, inspector `tools/inspect_iom6_spi_exchange.py`. Native inputs, source, model, and logs are pinned; proprietary originals/RAM remain outside Git.

## Next integration unit and remaining scope

First identify original host HCI header retries, pin 149/CE0 logical framing, and actual first HCI command/event requirements from source. Use that evidence to design a limited EM9305 protocol-state model and negative-response scenarios. Do not arbitrarily add data to create boot success. Display task notification, actual redraw producer, and normal external font-bank investigation remain separate conditions.

Web installation/independent recovery, full normal main startup, BLE lifecycle, 576×288 display, and real-device verification remain incomplete. Product fulfillment remains scope v2 13/29, 44.8%.

Follow-up bw272: [HCI framing contract](../communication/em9305-hci-framing-contract.md). After a positive header the original holds pin 149 low and stops at a new RDY consumer. Initial expected event is `04ff0101`, based on source/manufacturer index evidence. Actual payload, EM9305 state, and BLE boot remain unverified.
