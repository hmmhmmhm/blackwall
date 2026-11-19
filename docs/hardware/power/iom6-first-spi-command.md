# Original Main's First IOM6 SPI Command

Work bw-0270. Advancing one step from the [post-DCX boundary](../../firmware/main-display-integration-frontier.md), this identified the first SPI command and transmit data actually requested by original reset execution of stock 2.4, 2.3, and Faceclaw 38. Branches, PC, and returns were unchanged and no peer response was supplied. No physical device was accessed.

## New native boundary

`spiFullDuplexPreflight` can be used only when both existing IOM6 SPI storage and DCX no-pin profiles are explicit. Default is false. This profile allows SPI configuration 0/4 only; 4 stores FULLDUP bit 2. Existing blocking when the bus is busy remains. Transfer commands stop as `spi-full-duplex-command-unsupported` before being passed to the base engine.

| Input | New boundary PC | Write request |
| --- | --- | --- |
| Stock 2.4 | `0x582594` | `0x40056120 ← 0x201` |
| Stock 2.3 / Faceclaw 38 | `0x57b23c` | Same request |
| Stock 2.4 option-off control | `0x58258c` | Previous `SPICFG ← 4` boundary retained |

Existing event prefixes were retained for all three native original mains. SPI configuration=4, DCX=16, successful command=0, FIFO control=2, submodule=`0x21`, clock=`0x1201`. The off control exactly matches previous CPU, instruction count, and existing observations. Execution did not pass the command boundary or send bytes to an SPI peer.

## Actual requested data and original builder

Interpreting `0x201` with CMD fields from pinned Apollo510 DFP SVD gives WRITE=1, CE=0, TSIZE=2, CONT=0, OFFSETCNT=0, OFFSETLO=0. MSPICFG FULLDUP bit 2 places data in receive FIFO simultaneously with a write.

TX pointer in native stop context is stock 2.4 `0x2004ac74`, stock 2.3/CFW `0x2004891c`. Each RX pointer is four bytes earlier. The first two TX bytes on the actual stack are `81 00` for all three images. Initial RX word is 0. RX 0 is input state not yet overwritten, not a response.

The three TX storage words are `81 00 49 00`, `81 00 4a 00`, and `81 00 00 00`. The last two bytes are not transmitted data for this two-byte request. Sending the 32-bit storage width instead of TSIZE would incorrectly emit version-specific stack residue.

Original CMD builder is stock 2.4 `0x5811a4`; the other two images are recorded in the private report's source contract. The original builder alone was run in isolated M7 with the actual caller stack, CE/CONT state, and direction argument; all three returned `0x201`, matching native R2. Arguments and stack/return boundaries were supplied, while internal function instructions, branches, and return were not replaced. This isolated replay is not evidence of resuming M55 main or SPI transmission.

`81 00` matches the HCI read header in [EM9305 manufacturer material](https://www.emmicroelectronic.com/sites/default/files/products/datasheets/EM9305-DS.pdf). Manufacturer protocol half-duplex and Apollo master full-duplex configuration for header exchange are different layers. Actual G2 peer's first STS1/STS2, event queue, and RDY timing have not been observed or established. Ready values from the material are not injected to claim normal BLE boot. PDF version/acquisition limits follow the earlier integration-boundary document.

## Why the existing engine cannot be used unchanged

In pinned `BlackwallPollingIomEngine`, FULLDUP is a tag; SPI bytes returned by a write are not placed in receive FIFO. It also rejects a write CMD if outgoing FIFO is empty. The original driver instead writes CMD first and supplies data later with `FIFOPUSH`. Enabling only the configuration latch and delegating to this engine would not meet the actual request contract.

Even with TSIZE=2, the original driver pushes/pops FIFO in words, checks RX availability against at least 4, and copies only needed bytes from the final word to the buffer. The next model must therefore distinguish actual wire-byte length from FIFO word availability and padding. This source observation is not generalized to physical silicon FIFO timing verification. At this stage arbitrary FIFO values or completed transmission/reception are not supplied.

The next implementation unit is a combined SPI transaction contract: **CMD-before-FIFO → exactly TSIZE bytes sent/received → full-duplex RX FIFO → completion/IRQ/CS termination**, not simple per-register storage. Offset/CONT, unsupported formats, and absent peer must have explicit support status and be rejected before state changes. EM9305 responses are a separate explicit test-peer scenario, not a claim about actual device normal state.

## Verification and preservation

Outside Git under `~/Library/Application Support/Blackwall/simulator/`:

- `iom6-full-duplex-research-01`: prior IOM model, native unit runner, and inputs.
- `iom6-full-duplex-red-01`: frozen log failing from missing constructor before the new profile; absence of unit-pass marker preserved.
- `iom6-full-duplex-unit-01`: 21 native conditions for configuration readback, state preservation before command block, invalid value/width rejection, reset/power-off, and more.
- `iom6-full-duplex-dcx-regression-01`, `iom6-full-duplex-legacy-regression-01`: existing DCX 21 and initial IOM6 31 conditions. Reports and all file hashes for 73 conditions total were rechecked.
- `iom6-full-duplex-main-01/{stock24,stock23,cfw}` and `iom6-full-duplex-control-01/stock24`: four original-main native runs, performed sequentially with terminal results confirmed for all.
- `iom6-full-duplex-saved-audit-01`: execution/semantic audits passed for all four saved runs. Native was not rerun for the audits.
- `iom6-first-spi-contract-01`: actual native context, stack/SVD analysis, and original builder replay.
- `iom6-first-spi-verification-01`: inspector, 15 local dependencies, and verification manifest.
- `iom6-first-spi-contract-02`: report reanalyzed with pinned dependencies, byte-identical to `-01`.

Tools are `tools/iom6-full-duplex-preflight-candidate.json` and `tools/inspect_iom6_first_spi.py`. The candidate uses a schema 2 semantic contract and changes only model and explicit board options without changing runtime observation. Original images/private RAM remain outside Git.

Integrated BLE, normal main startup, 576×288 display, and actual installation/recovery remain incomplete. Product fulfillment remains 13/29, 44.8%, scope v2.

Follow-up bw271: [SPI word transaction](iom6-spi-word-transaction.md). Original M55 mains from all three images completed an explicit one-shot `8100/c000` transaction and copied it into the actual RX buffer. The next request stops from exhausted budget; actual EM9305 state, physical CS, BLE boot, and integrated display remain unverified.
