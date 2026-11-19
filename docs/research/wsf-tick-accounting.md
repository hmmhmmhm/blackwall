# Original WSF Tick and Timeout Timing Difference

bw406. **The 9.760541 seconds in bw405 is explained by the currently declared clock profile and original tick accounting.** Original code, model, clock, and timer settings were not changed. Physical time accuracy or an SI 10-second expiration was not verified. Overall 7/16 (43.8%), E14 partial, and API 3/6 remain unchanged.

## Clock and original calculation

The existing STIMER log shows CFG `0103`/32768 Hz. The pinned generated model also specifies 32768 Hz for XTAL32K selection. Original STIMER port initialization stores 32 in period variable `2007745c`. The IRQ32 catch-up function divides elapsed STIMER counts by this period and passes the result to the original kernel tick function, which increments the RTOS tick at `20077660`.

Thus, in this declared profile, the RTOS tick runs `32768 / 32 = 1024` times per virtual second. The existing bw405 final SRAM alone confirmed an increase of 10223 RTOS ticks over 9.9831492 virtual seconds. A native run was not repeated to create this evidence.

Original WSF dispatcher `4d7d44` integer-divides the difference between current RTOS tick and prior WSF reference `20077b3c` by 10 and passes it to `WsfTimerUpdate`. After processing, it updates the prior reference to the current RTOS tick. The original seconds wrapper multiplies 10 by 100 to set 1000 WSF ticks. Whether this combination equals 10 SI seconds is a separate question.

## Actual trace

One new original execution used the same lost-response input as before. Only SRAM reads and observation at HCI timer-start and WSF update entry/return were added. The host did not change original instructions, branches, registers, or peripheral state. Existing return and guard stop boundaries were retained.

The RTOS tick at timer-start was 6371, and the previous WSF reference was 6360. Three actual updates were:

| Current RTOS tick | Previous reference | Difference | Original update argument | Discarded remainder | Remaining WSF ticks before → after |
| ---: | ---: | ---: | ---: | ---: | --- |
| 6375 | 6360 | 15 | 1 | 5 | 1000 → 999 |
| 13816 | 6375 | 7441 | 744 | 1 | 999 → 255 |
| 16366 | 13816 | 2550 | 255 | 0 | 255 → 0 |

The original subtracted exactly `1+744+255=1000` WSF ticks. Accounting for the 11 RTOS tick reference difference before start and six discarded remainder ticks, actual RTOS elapsed after timer-start was:

`1000 × 10 + 6 − 11 = 9995 RTOS tick`

This equals actual `16366 − 6371`. The new trace contains three updates with no overflow. The callback ran on the same WSF message/event 1 and original task/stack as before.

## Comparison with virtual time

At 1024 Hz, 9995 ticks equal 9.7607421875 seconds. The observed callback time was 9.760541 seconds, a difference of 201.1875 µs. The RTOS tick/virtual-time residual at each update was also within one RTOS tick (976.5625 µs). This is not a finer-grained validation separating sampling phase and IRQ/handler progress.

The 239.459 ms difference between 10 seconds and the observed value breaks down under the current profile as follows:

| Component | Difference |
| --- | ---: |
| Interpreting 10000 RTOS ticks at 1024 Hz | 234.375 ms |
| Net difference of five ticks from pre-start epoch and integer remainders | 4.8828125 ms |
| Residual between counter sample and callback time | 0.2011875 ms |
| Total | 239.459 ms |

Do not change the clock to 32000 Hz or increase the original timer value to match the number. First reproduce original values in the current profile. No claim is made that actual physical clock, temperature, or calibration matches. Distinguish `tick_accounting_verified=true`, `physical_clock_accuracy_verified=false`, and `si_ten_second_timeout_verified=false`.

## Additional observation control and limits

The additional tick-observation-on run used the same main, model, board, and initial input as the existing bw405 tick-observation-off run. Complete SRAM after ATT, disconnect, and final state and values in the four existing JSON reports matched. Final R0–R15, timeout time, callback arguments, and guards also matched within existing reports. Raw JSON bytes were not identical, so false was recorded separately from value equality.

This compares the **collected state** for an additional observer under this pinned input. It does not guarantee all special registers, all peripheral internal states, noninterference of the existing HCI observer itself, or other scenarios. Unverified flags in prior manifests/reports were not retroactively changed.

Recovery still stops at the controller single-use replay guard after the callback's fifth subsequent call. Completed recovery, consumption of the final app error notification, and native timeouts in other originals remain unverified. Next, pin actual controller reinitialization prerequisites, reset generation, and allowed replay scope.

## Verification material

Eighteen checks in `verify_wsf_tick_accounting.py` confirmed the original period/IRQ/kernel/divide-by-10 byte path, actual subtraction, epoch/remainders, clock range, and equality of existing full SRAM and report values. Three mutations of update arguments, tick period, and starting epoch, consistently propagated through JSON/log/hash, were rejected. Fourteen progress-management checks also passed.

The first audit failed because its kernel-instruction window included a later compare instruction. The exact four-instruction increment sequence was identified and only the audit corrected; the original was not rerun. The failed verifier and evidence were retained.

Tools: `renode-wsf-tick-observer.cs`, `probe_wsf_tick_accounting.py`, `verify_wsf_tick_accounting.py`. Private evidence: `wsf-tick-accounting-native-01`, `wsf-tick-accounting-research-01`. No physical device, Astra/subagent, or external publication occurred.
