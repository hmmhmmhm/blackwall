# STIMER Virtual Time, Counter, and Compare Model

Work bw-0155. Original ARM in stock 2.4, stock 2.3, and Faceclaw configured STIMER at 32768 Hz and executed until the counter was increasing. The next boundary is a write of `8400` to PWRCTRL DEVPWREN `40021004`. Full main loop, display, and physical timing/installation/recovery remain incomplete.

## Reused engine and explicit differences

MIT-licensed Renode [AmbiqApollo4_SystemTimer](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/Timers/AmbiqApollo4_SystemTimer.cs) was obtained at pinned commit `066a7f13c052215632d469c995c89aea37c573b1`. Original SHA-256 is `01759fe4e1066245743a8b09645a5f905f80b22df631452252d535867d2f38f3`. It was checked against the existing pinned Git tree blob; original, manifest, and full MIT license are preserved in private `simulator/stimer-engine-research-01`. The license was also added to generated evidence folders. This supplemental asset does not affect the eight execution inputs.

The original is not used unchanged. `tools/stimer_engine_source.py` checks original hash and change locations, then applies these transformations to generate `BlackwallStimerEngine`, preserving copyright/license notices:

- Remove forced `systemTimer.Increment(3)` on compare write. Counter changes only through Renode time or firmware's allowed frozen-counter writes.
- Set XTAL to 32768/16384/1024 Hz and LFRC to declared nominal 900 Hz according to public Apollo510 definitions. HFRC 6 MHz/375 kHz is also used. Actual oscillator, power, and calibration state were not verified.
- Correct the original path that could keep running at a previous valid frequency after NOCLK selection, so it stops.
- Set 32-bit counter/compare timer period to 2^32 ticks and test wrap.
- Add a path to load the counter under FREEZE. Counter remains 0 while CLEAR is held.

**Compare writes use an immediately applied relative-delta model.** Public [register documentation](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/stimer_regs.html) describes writing the number of future ticks to SCMPR and reading the calculated absolute counter value. Clock-domain write and IRQ delays handled by HAL are not physically reproduced. Removing forced counter increments does not imply hardware timing agreement. Subcycle phase on clock switching and asynchronous boundaries were not physically verified either.

## Strict adapter

`BlackwallStimerClockCounter` requires explicit `nominal-source-clocks`. Existing interface/core/interrupt-storage models remain unchanged; only the new engine and adapter were added.

- Expose selected 32-bit operations on STCFG, STTMR, SCMPR0–7, and interrupt bank.
- Permit only documented STCFG fields. Reject CTIMER input clocks 7/8 and reserved clocks/bits.
- Permit counter writes only with FREEZE=1 and CLEAR=0.
- Capture configuration/data addresses are unsupported. Software interrupt set/clear differs from actual GPIO capture.
- Continue blocking set/clear alias reads, unsupported status assignments, and narrow/unaligned accesses.
- Connect nine engine outputs for compare A–H and capture/overflow to NVIC32–40. Standalone verification reaches NVIC pending for compare A and overflow only; it does not verify all comparators, capture, or actual ISR completion.

Fixture reset delegation uses the existing lifecycle contract; unit tests confirmed initialization of counter, configuration, and IRQ state. Unselected controls retain existing interrupt storage.

## Verification and original ARM results

Unit 01 failed because the new adapter was unimplemented. Units 02/03/04 were preserved in order; final unit04 passed 33 checks. A synthetic spin guest advanced Renode virtual time in integer microseconds.

- 6 MHz: 1 µs=6 ticks; 375 kHz: 8 µs=3 ticks.
- Declared nominal clocks: 32768/16384/1024/900 ticks respectively in one second.
- FREEZE, retained CLEAR, NOCLK stop, frozen-counter load, and state preservation on invalid writes.
- Compare writes do not force time forward; relative-delta read values, pre/post-match status, and NVIC32 pending.
- 32-bit wrap and overflow NVIC40 pending.
- Writing relative delta 5 at FFFFFFFD reads as 2; after six ticks counter=3/status=101 with new NVIC32/40 pending.

Original input used the immediately preceding interrupt main03. Pinned bundle/raw main, initial fills, execution policy, and all existing model sources were preserved; only engine, adapter, selected board, and observation output were added. Original instructions, branches, and returns were not forced. This begins at existing main reset, not evidence of ROM/full boot.

| Condition | Observed clock state | Next boundary |
| --- | --- | --- |
| Stock 2.4 / nominal clock | CFG0103, 32768 Hz, counter 26, status 0 | 40021004 write 8400 |
| Stock 2.3 / nominal clock | CFG0103, 32768 Hz, counter 31, status 1 | Same |
| Faceclaw38 / nominal clock | CFG0103, 32768 Hz, counter 31, status 1 | Same |
| Stock 2.4 / existing storage | Clock model unselected | Existing 40008800 read |

Selected conditions have 15 reads/four writes and Enable 1. IRQA is also high when status is 1. These are observations under selected virtual clock/execution conditions, not measured time or firmware performance comparisons. In particular the 2.4 versus 2.3 difference is not interpreted as a CFW effect. Stock 2.3/CFW were compared with identical model/runtime. **Original ISR execution is unverified**; neither its occurrence nor absence is asserted.

The 110 saved audits in `verify_stimer_clock_evidence.py` passed. They compared public clock enums and ARM compile offsets, source/engine/license pins, current model/unit phases, original four/full model reconstruction/observation-only runtime/fills/control/existing core invariance. Current core and existing interrupt storage match immediately previous verified source, so those regression results were reused. Unchanged RTC/PMIC tests were not repeated to avoid duplication.

Evidence: private `simulator/stimer-clock-unit-01~04`, `stimer-clock-main-01`, `stimer-clock-verification-01`. A reading-review gap in wrap compare tests was addressed by unit04. Limits remain for all eight comparators, capture, physical delays, and original ISR. Review inherited the parent model; Astra and transcript archive audit were not performed.

The next `8400` requests MSPI1 (bit 15) while including UART1 (bit 10) in the pinned header. The current model has not allowed that write; next investigate MSPI1 power, initialization path, and peer role. Product completion remains 13/29 (44.8%). No glasses connection, RAM payload, OTA, permanent write, or Astra execution occurred.
