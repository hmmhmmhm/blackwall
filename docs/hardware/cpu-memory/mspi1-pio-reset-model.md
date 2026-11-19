# MSPI PIO and Idle NOR Reset Model

Task bw-0168. This is the first zero-data PIO device model based on the [source contract](mspi1-pio-reset-contract.md). The overall web installation, recovery, CFW, simulator, and integrated display goal was in progress; product acceptance criteria were 13/29 (44.8%).

## Implemented state

Uses the optional PIO interface in `renode-mspi1-config.cs` and `renode-mspi1-pio.cs`. Without selection, the prior CTRL C1 strict boundary remains. The explicit `idle-nor-reset` profile handles zero-data TX commands with observed DEV0CFG `01410061` and CTRL C1. Supported device commands are 66, 99, and NOP 00. It supplies no unknown ID, address/data transfer, DMA, or NOR backing.

START clears prior completion and enters busy. When a separate Renode virtual-clock LimitTimer expires, controller STATUS and CMDCMP are set. Completion is not driven by read count. SPI byte-transfer completion has no device ACK; device state transitions are handled separately. 66 sets the reset latch, NOP invalidates it. 99 enters NOR reset recovery only with the latch set; without it, the ignored count is recorded. Controller completion and the end of NOR recovery are separate events.

Transfer 10 µs and NOR recovery 100 µs are **selected test assumptions**. They were not verified as actual bus frequency, waveform, a specific column in the manufacturer timing table, or installed-chip behavior. Passing with these values does not establish physical reset success. Reset during program/erase is outside the model's scope.

Config changes while busy are strict. The clock-storage value-change epoch is saved at transfer start; if it changed by completion, the transfer aborts. Thus an off → on recovery before the deadline does not complete the transfer. Rewriting the same value leaves the epoch unchanged. This is the selected **abort-on-change policy**, not evidence of how the actual controller pauses/resumes when the clock changes. Owner reset initializes both timers and PIO/IRQ state.

Hardware CMDCMP updates status/IRQ through `SetPending`. Hardware events are not added to guest MMIO Writes. Original INTSET software writes and strict mask policies remain.

## Verification history

- unit01: red phase; platform loading failed because the implementation class was absent.
- unit02: 21 passed. unit03: 23 passed after adding busy-config rejection and clock-off retention conditions.
- Review finding: checking only Ready at completion missed intermediate off → on, and hardware events were mixed into guest Writes. Fixed using an epoch and dedicated event path.
- unit04: 23 transient off → on abort checks passed. Final `mspi1-pio-unit-05` adds same-clock-value rewrite, hardware-event/MMIO counter separation, and NVIC21 pending for 26 checks.
- `mspi1-pio-stuck-01`: 12 passed. With the completion timer explicitly disabled, busy/incomplete and no NOR latch remained after 1,000 µs. This did not execute original firmware timeout/fallback.

The first `mspi1-pio-main-01` predates the review fix and is preserved. Final original replay and audit using current source are recorded separately below. There was no physical device access, flash, or persistent write.

## Final original replay and regressions

All four conditions in `mspi1-pio-main-02` completed. Each of three originals had starts/completions 2, reset 1, reads/writes 2, abort/ignored-reset 0, final CTRL=C2, and busy/latch/recovering=false. This is evidence that 66/99 were handled in order under the current limited command set and original caller path. It is not evidence of actual SPI wire activity, device acceptance, or physical reset.

The next stop was a `0x205ED` write to DEV0XIP `0x40061090`: stock 2.4 PC=`4E75D6`, stock 2.3/Faceclaw PC=`4DA202`. The existing guard rejected this further change to already-enabled XIP configuration. No arbitrary flash backing or fake success was supplied. The control without PIO stopped at the existing CTRL C1/PC `4E8A46`.

For all three originals, confirmed IRQ guest Writes 10, all-clear 4, IER `1A80`, status 0, and IRQ low. Stock 2.3/Faceclaw used identical model, board, and runtime conditions except for main length. Original main bytes, vectors, and existing execution policies were retained. Earlier synthetic chip-revision, power-ready, ADC, and other conditions remain.

`mspi1-pio-regressions-01` reran existing all-clear 82 and clock 16 against current combined source; all 98 passed. The 75 checks in `mspi1-pio-verification-02` compared current source, unit 26/stuck 12, phase/time, original bytes, derived hashes, markers, next guard, control, equal 2.3/CFW conditions, and regression evidence. Earlier audit 01 had 65 checks; 02 added three IRQ-semantics and seven regression checks.

The inherited-parent-model review's clock-transient/MMIO-counter findings were fixed and reverified. The review did not use Astra or another model family and was not a full transcript audit. Full ROM/bootloader boot, BLE, NOR data, integrated display, and physical recovery remained incomplete.
