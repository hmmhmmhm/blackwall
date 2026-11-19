# Original Main Display Wait Conditions and SPI Integration Frontier

Work bw-0268. Distinct from prior diagnostic-caller render/IRQ/RTOS return, the next boundary of main executed from original reset was identified. Original code, branches, and returns for stock 2.4.0.24, 2.3.0.24, and Faceclaw 38 were unchanged. No physical device was accessed.

## Progress in original main

In pinned Apollo510 DFP `apollo510.svd`, IOM0 DCXCTRL has offset `0x124`, reset 0, mask `0x1f`. DCXEN is bit 4 and DCXSEL bits 3:0 select a CE channel. Original write `0x10` enables DCX without selecting an output channel. Only this limited latch state is supported by optional `spiDcxNoPinsStorage`. DCX pin signals, transfer engine, and peer responses were not implemented.

The new option is allowed only with IOM6's explicit SPI storage profile. Default off retains existing blocking. Other CE selections, reserved bits, and invalid access widths are rejected before state changes. Reset and power-off clear the latch. Transfer commands remain unsupported.

| Input | Previous DCX write PC | New SPI configuration write PC |
| --- | --- | --- |
| Stock 2.4 | `0x58253a` | `0x58258c` |
| Stock 2.3 / Faceclaw 38 | `0x57b1e2` | `0x57b234` |

All three mains pass `0x40056124 ← 0x10` and strictly stop at `0x40056280 ← 4`, the next master full-duplex configuration request. Successful SPI command count is 0 for all three, and SPICFG's value before application is also 0. FIFO control=2, submodule=`0x21`, clock=`0x1201`. Existing observed event prefixes were preserved. Option-off control CPU, instruction count, and existing observations exactly matched the earlier run.

## Actual display-task wait conditions

Full SRAM/ITCM from existing `original-main-full-memory-02` was reused. After confirming the 40-byte software frame and optional 64-byte high-FP frame from original PendSV instructions, hardware frames and caller stacks were interpreted. No new original ARM execution or forced task wake occurred.

| Task | Observed wait condition across three images |
| --- | --- |
| `ui_task` | Queue with receiver 1, messages 0; capacity 96, item size 12 bytes |
| `displaydrv_mgr_task` | Index 0 notification-bits wait, mask `0x800000`, value 0, waiting state 1 |
| `ambiqdraw` | Index 0 notification-counter wait, clear-on-exit 1, ticks `0xffffffff`, value 0, waiting state 1 |

UI queue address is `0x20074e10` in stock 2.4 and `0x20075868` in stock 2.3/CFW. Saved R6 and actual event-list container were compared together. Both notification types were checked through actual BL targets in caller stacks and original argument-saving prologues. A saved buffer candidate address was not assumed to be a queue handle.

This evidence does not support a claim that completing BLE initialization automatically advances display. Next locate producers and meanings of 12-byte UI messages and both notifications in original code. Current investigation did not verify message structure or producers.

## EM9305 manufacturer material and unknowns

Web-extracted text of the [manufacturer EM9305 datasheet](https://www.emmicroelectronic.com/sites/default/files/products/datasheets/EM9305-DS.pdf) is v4.5.3, 2025-08-20. Section 8.8 describes HCI SPI read `0x81`, write `0x42`, ready STS1 `0xc0`, and stage-specific CSN/RDY meaning. Protocol half-duplex semantics are distinct from Apollo master full-duplex configuration used for header exchange. This alone does not establish G2 chip revision, physical timing, or current peer state.

It was distinguished from earlier lowercase-filename v4.5.1. Direct PDF download failed by timeout/HTTP2 error; visual review of diagrams and local PDF hash pinning were not completed. Web-extracted text research informs the next SPI contract and was not used to inject current peer responses.

## Reproduction and verification material

Preserved outside Git under `~/Library/Application Support/Blackwall/simulator/`:

- `iom6-dcx-no-pins-main-01/{stock24,stock23,cfw}`: pinned plan, model, originals, logs, native results.
- `iom6-dcx-no-pins-control-01/stock24`: default option-off control.
- `iom6-dcx-saved-audit-01`: all four saved runs passed execution/semantic audits without reruns.
- `iom-dcx-no-pins-unit-01`: 21 native conditions. `iom-dcx-legacy-regression-01`: 31 existing-profile conditions. All file hashes in both reports were rechecked. Preimplementation red is preserved in `iom-dcx-no-pins-red-01`.
- `main-display-wait-map-01`: first analysis of three images/nine tasks.
- `main-display-frontier-verification-01`: inspector and 13 local dependencies, SVD extraction/hash, unit hash-check records.
- `main-display-wait-map-02`: reanalysis with pinned dependencies, byte-identical to first report without native rerun.

Saved native audits use `tools/run_native_candidate.py --audit-existing --audit-output` and `tools/iom6-dcx-no-pins-candidate.json`. RAM inspector is `tools/inspect_main_display_waits.py`. Frozen dependencies are for reproducing historical analysis and are not silently replaced with current code.

## Next integration units

1. Identify code actually enqueuing to the original UI queue and the 12-byte message contract. Trace display/ambiqdraw notification producers too. Do not substitute synthetic messages or forced task wakes for normal main progress.
2. Model IOM master full-duplex configuration and first command/FIFO/CSN/RDY exchange together using manufacturer/Apollo material and exact original code. Do not create completed communication from register storage alone.
3. Connect normal external font-bank supply/version contract and full main's actual display calls. Existing diagnostic glyph success is not replacement evidence for normal assets or a 576×288 integrated display.

Full normal main startup, BLE operation, integrated display, web installation/independent recovery, and real-device verification remain incomplete. Product completion remains 13/29, 44.8%, scope v2.

Follow-up bw269: [original UI producer contract](../hardware/display-gpu/ui-queue-producer-contract.md) confirmed type 7 queue/ring send/receive, waiter release, and consumer prefix. Actual redraw producer, notification, and integrated main remain incomplete.

Follow-up bw270: [first IOM6 SPI command](../hardware/power/iom6-first-spi-command.md). Original main across three images requests `CMD=0x201`, TX `81 00`. After FULLDUP configuration, command remains blocked before transfer with commands=0. Next is a transaction model combining CMD-before-FIFO, full-duplex, TSIZE, and word FIFO.
