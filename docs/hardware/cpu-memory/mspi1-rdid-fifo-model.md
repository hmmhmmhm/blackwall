# Explicit NOR Identity Profile and RX FIFO

Task bw-0172. Overall acceptance criteria remained 13/29 (44.8%). This did not identify the chip installed in an actual G2; it verified original ARM receive/copy behavior using an explicit peripheral profile matching the [manufacturer contract](mspi1-rdid-contract.md).

## Implementation

`identityProfile` in `BlackwallMspi1PioReset` defaults to `none`. Only explicit `mx25u25643g` supports RX3 with CFG `03010861`, command `9F`, CTRL `30441`. It uses C2/25/39 from manufacturer Table 6 and offers no option to change the ID according to firmware success criteria. Other device identities, status registers, and flash backing are unimplemented.

The transfer uses the existing 10 µs virtual-time test assumption. After completion RXENTRIES becomes one word, consumed by reading RXFIFO. The final little-endian word is `003925C2`; unused high byte 0 is model padding, not NOR data beyond three bytes. Reads before completion or from empty FIFO, overwriting an unconsumed frame, and unsupported lengths/commands remain strict. Owner reset cancels pending FIFO and timers; clock epoch changes abort.

Changed the PIO read interface to accept an offset argument and updated the config caller too. No separate host RAM write or CPU PC/return-value change was added. Scope is one short FIFO frame and CMDCMP; this does not implement full FIFO capacity/streaming, RX threshold IRQ, underflow hardware flags, or DMA.

## Unit and regression tests

- unit01: red phase; platform load failed without the identity constructor option.
- `mspi1-rdid-unit-02`: 30 passed. Checked ID order/padding, entry count/consumption, rejection before completion, empty FIFO and pending overwrite, reset, and clock-transient abort.
- `mspi1-rdid-none-01`: five checks. Default `none` rejects the RX3 request and generates no response.
- `mspi1-rdid-stuck-01`: 19 checks. With no completion timer, no FIFO data appears even after 1,000 µs. This did not test original firmware timeout/fallback execution.
- `mspi1-rdid-regressions-01`: 89 passed against current combined source: prior PIO 26 and mixed 63.

## Original ARM execution

`mspi1-rdid-main-01` contains four conditions: original stock 2.4, 2.3, and Faceclaw plus an identity-none control. Existing vectors, main bytes, CPU/memory policy, and equal 2.3/CFW conditions were retained. Runtime added only a bounded read-only observer at the actual FIFO-helper return point.

All three originals showed RAM word **`403925C2`** at the first FIFO return point. High byte `40` from the preceding value `40061088` was preserved while only the low three bytes became C2/25/39. Thus the original CPU tail-copy code actually executed; the host did not write the ID to RAM.

After 288 RDID frames it stopped on the next request with a new capture setting. Model counters were starts/completions 290 (including two prior reset commands), RDID/FIFO reads 288, pending 0, busy=false. Not all 288 RAM copies were captured; distinguish the first snapshot from point hits.

At the stop, CFG changed `03010861` → `03410861`, only RXCAP bit 22; INSTR 9F/RX3 CTRL `30441` was unchanged. The new capture setting was unsupported, so strict blocking remained. PCs were stock 2.4=`4E8A46`, stock 2.3/Faceclaw=`4DB672`. The original caller's timing-check area and HAL TIMING_SCAN_SET path contain RXCAP/TXNEG/RXNEG and delay settings, and debug literals in that original area also indicate timing scan. This is not measurement of an actual signal timing window.

The observer's full event list had capacity 128, sequence 575, and 447 dropped. First snapshots/hits per point were preserved separately and provide byte-copy evidence, but do not constitute a full execution trace. Identity `none` stopped at the existing RX3 start boundary with zero FIFO-return hits, no snapshot, and zero RDID frames.

The 89 checks in `mspi1-rdid-verification-01` compared current source, three unit fixtures, virtual phases, original bytes, derived hashes, profile/default, observer-only runtime changes, first three-byte copy/fourth-byte preservation, bounded-trace limits, new RXCAP boundary, equal 2.3/CFW conditions, and regressions. Aperture accesses were 0 and no unknown flash backing was provided.

## Next steps and incomplete work

Next compare original timing-scan configuration combinations, repetition conditions, success criteria, and RXCAP semantics. Distinguish a functional ideal SPI profile from an actual timing window. The current ID was not changed and capture checks were not skipped.

Existing chip-revision, power-ready, ADC, virtual bus/recovery timing assumptions remain. Full boot/main loop, BLE, NOR contents, integrated display, and physical installation/recovery remain incomplete. This work did not connect glasses, flash, or write persistently.

An inherited-parent-model review found no additional material issues. It did not extend the result to verification of the installed chip, actual timing window, or full IRQ state, and distinguished 288 frames/hits from one first snapshot and bounded event drops. No Astra, other model-family review, or full transcript audit was performed.
