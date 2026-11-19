# RTC write lifecycle during sustained execution

bw495 in progress. V1 matrix passed two six-second runs for each of three originals, but first stock24 60-second run stopped 7.449760 seconds post-screen. PC0x507074 and R0=0x40004820 match original RTC LOW store. Board `halLowUpperWrites:false` rejects this write. Earlier `faults` aggregation omitted delegated RTC `AccessCount`, so CPU fault/upper guard 0 must not be interpreted as zero unsupported accesses overall. Failure was preserved without automatic retry.

This change is limited to virtual RTC and observation. Original branches/returns/TCB/RAM and physical glasses are unchanged. Default strict counter-write disabled/weekday congruence rejection remains.

## Original inputs and reference evidence

Actual SRAM HAL time structure immediately before stop had weekday 0, century 1, year 0, month 1, day 1. `2000-01-01` is Saturday 6 in DateTime, so merely enabling counter writes could still hit existing `TryDate` additional congruence check. Seconds value 16 follows original path forming LOW register 0x1600. This is source-supported analysis of raw snapshot and original instructions; RTC LastError was not collected at the time.

Pinned Apollo510 HAL `am_hal_rtc.c` SHA `faccd6d5…` range-checks weekday 0..6 and records it as a field separate from date. SDK time structure field order and original writer LOW→UP construction were compared. Pinned Renode engine also warns about date/weekday mismatch, whereas Blackwall strict adapter required equality. This material does not certify all actual Apollo510B silicon calendar/weekday/alarm behavior.

## Explicit functional profile

`BlackwallRtcAdapter(..., independentWeekday:true)` can be used only with `halLowUpperWrites:true`. Valid BCD, century, actual date, weekday 0..6, WRTC, LOW→UP staging, and busy conditions remain checked. Even if it differs from calendar date, supplied weekday is preserved independently and advances modulo 7 by number of virtual calendar date changes. LOW/UP read pair returns weekday from same snapshot. Reset clears anchor and mismatch count. This does not newly support all weekday-based alarms or physical clock accuracy.

Default strict remains; only explicit `--rtc-profile independent-weekday` replaces one verified prior RTC component and two board options. Before/after component bytes, unit proof, and board substitution are recorded in plan/audit. Host does not change weekday written by G2 or force a date.

Prior six-second evidence across three originals remains historical for previous profile. After changing integrated profile, six/60-second repeats must be reverified under new pinned configuration. Do not overwrite earlier failure as success or reduce denominator 10.

## Verification and observation

`tools/verify_rtc_weekday.py` adds six cases to 44 existing RTC regressions: independent commit/weekday preservation, midnight carry, weekday 7 rejection, recommit with matching date, reset. First import assembly issue was preserved as fixture error; next red was actual missing three-argument constructor. Green01 passed all 50 on actual Renode spin guest/virtual time, not full original G2 main completion.

Sustained runner exports RTC AccessCount/LastAddress/LastValue/LastError, control, pending, writes, commits, and virtual date, and includes RTC in fault aggregation. First run the same original 60-second control without selecting new profile to confirm rejection cause in actual metadata. This expected-failure experiment is not counted as 60-second success. Next is original main run with new functional profile.

Private: `sustained-matrix-bw492-01/native/stock24-60s-r1` (old failure), `rtc-weekday-{red-01,red-02,green-01}` (fixture/functional red/green), `sustained-rtc-control-native-01/stock24` (control). New ARM main 60-second success was not yet confirmed. Physical device/Astra/external publication 0.

Follow-up control confirmed rejection with actual metadata: 7.449566 seconds / RTC AccessCount 1 / LastAddress 40004820 / LastValue 1600 / LastError counter-low-precondition / control 1 / commit 0. Other fault counters 0; semantics rejected both target_reached and fault_free. This negative control is not included in 60-second goal success.

Primary sources: [pinned Apollo510 HAL](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_rtc.c), [pinned Renode RTC engine](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/Timers/AmbiqApollo4_RTC.cs).

Final follow-up: original stock24 with new profile passed previous boundary with RTC commit 1/RTC guard 0/LastError none. At 8.160403 seconds it stopped at next GPIO/EM9305 ready input 40010410/PC501676. Initial speculation calling this UART0 was corrected using source GPIO117 owner/bit21/original literal. Proof is private `sustained-rtc-lifecycle-proof-01/report.json`; full 60-second success false.
