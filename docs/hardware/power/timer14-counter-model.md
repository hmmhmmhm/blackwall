# Timer14 Counter Model

Work bw-0165. Overall product completion remains 13/29 (44.8%). Web installation package, recovery verification, and integrated display remain incomplete.

## Implementation and evidence

TIMER at `0x40008000` and STIMER at `0x40008800` are separate blocks. Public Apollo510 SVD and CMSIS header confirmed Timer14 CTRL/COUNTER/CMP0/CMP1/MODE addresses `0x400083C0..3D0`, GLOBEN bit 14, INTEN/STAT/CLR/SET bits 28/29, and IRQ81. The 38 checks in `inspect_timer14_contract.py` also compare source hashes, Git blobs, ARM C compile offsets, and original main's first CTRL14 read/disable code.

The reused engine is `AmbiqApollo4_Timer.cs` (MIT) from Renode infrastructure commit `066a7f13c052215632d469c995c89aea37c573b1`. Original source/license and hashes are preserved outside Git in `simulator/timer14-research-01`. `timer14_engine_source.py` checks hashes and adapts CLOCK 9 bits, TMODE position, trigger width, reset, and nominal LFRC for Apollo510. Wrapper `renode-timer14.cs` exposes only required Timer14 functions.

Supported scope is EDGE function, XT 32768 Hz or nominal LFRC 900 Hz, continuous counter with CMP0=FFFFFFFF, nonzero CMP1, enable/disable/global gate/clear, and selected interrupt status/W1C/W1S. Disabled counter load is also used in mock tests. Other timers, output/PWM, triggers, finite primary periods, and DMA remain strict. Time does not advance by counting CPU register reads.

## Failures and timing precision

After correcting an initial unit02 compile error, unit03/04 observed 6 against expected wrap value 7. unit05, restoring ComparingTimer limit to FFFFFFFF, stopped at counter 0 due to zero-period scheduling after compare==limit. These attempts are not recorded as success.

Diagnostic `timer14-wrap-diagnostic-01` observed FFFFFFFE → FFFFFFFF → 0 → 1 and continued increments with XT time at limit=2^32. Pinned commit `ComparingTimer.cs` and `BaseClockSource.cs` showed fractional residue discarded on rescheduling and events. Final model uses exclusive period=2^32. At an exact nominal-time endpoint, count may appear one tick late after an event. unit06 explicitly allows 1 µs margin for wrap/secondary event phase, retaining exact tick checks in other non-event clock phases. This does not prove physical clock or cycle-exact device behavior. Accumulated error over repeated events and phase agreement of the two comparators are unverified; no guarantee limits total execution error to one tick. STIMER code was not changed; compare-event precision is a future audit subject.

## Execution evidence

- `timer14-unit-06`: 27 checks with a synthetic spin guest. XT/LFRC, retained clear, unchanged reads, disable/resume, global gate, wrap, masked compare latch, NVIC81 pending, reset, and unsupported rejection. This is not evidence of actual Timer14 ISR execution.
- `timer14-main-01`: three original ARM inputs and a control without Timer14, four conditions total. Original files, vectors, and existing execution policy were preserved. Stock 2.3/Faceclaw retain identical model/runtime and differ only in main length.
- All three originals end disabled with CTRL=A10, CMP0/1=FFFFFFFF, nine writes, XT selected. Stock 2.4 count 2/reads 59; stock 2.3/Faceclaw count 3/reads 9. No speed difference or CFW effect is inferred.
- Next stop is MSPI1 INTCLR `0x40061208` write of FFFFFFFF. It exceeds the existing 14-bit mask and was not automatically allowed. PC is 4E8A3E for stock 2.4 and 4DB66A for stock 2.3/Faceclaw.
- Control without Timer14 stops as before at CTRL14 read `0x400083C0`/PC 5070D4.

Existing synthetic power, ADC, chip revision, and other assumptions remain. This ran from original main reset; full boot including ROM/bootloader, actual BLE/MSPI transfer, external NOR backing, integrated display, and physical recovery were not confirmed. No glasses access or installation occurred.

## Regression and review

MSPI IRQ 73 (`timer14-regressions-01/mspi1-interrupts-unit-02`) and latest STIMER 33 (`timer14-regressions-02/stimer-clock-unit-04`) were rerun using current combined source. Older STIMER unit01 in regression01 actually passed 27 checks but failed because the inspector expected 33. It was corrected with latest fixture04; already-passed MSPI was not repeated. Saved evidence audit `timer14-verification-02` compares 65 items for source, originals, guards, controls, and regressions. Audit01 warning rejection resulted from a runtime cache-clamp notice; 02 excepts only that exact wording. The global native parser was unchanged.

Review inheriting the parent model found no significant guard/state error. It requested that event-margin checks not be described as exact-deadline passes and that unverified repeated accumulated error/comparator phase be stated; this was incorporated. No Astra or other model-family review or full conversation transcript audit was performed.
