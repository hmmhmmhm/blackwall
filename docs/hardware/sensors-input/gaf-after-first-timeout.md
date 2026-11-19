# Request 4 and Watchdog After the First GAF Timeout

bw-0430. **Original stock 2.4 sends request 4 even after request 2 returns −4, and a watchdog reset request occurs first during the second wait.** Cleanup and setter return were not observed under this explicit virtual profile. Do not disable the watchdog or raise the timing profile again to force cleanup.

## Subsequent original branch

Original `0x55496e` ORs the first error into R4, then sets R1=4 and R0=device and calls the same request helper at `0x554974`. The original helper repeats request RAM write, RMW, 200 µs delay, and wait. Cleanup follows the second helper return at `0x554978`. The setter epilogue is `0x554c64`.

The existing capture's process had exited, so full CPU/peripheral state could not be resumed. Rather than claiming a resume by filling SRAM or PC, a new run replayed the same prefix once and included subsequent observations. Only the first-stop observer was changed to one-shot to avoid stopping again on the same instruction. Four subsequent observation points cover request 4 call/return, cleanup entry, and setter epilogue; they do not replace original instructions.

## Observations in one actual run

| Stage | Observed |
| --- | --- |
| First wait/helper/setter continuation | Same 200,000 iterations, R0 −4, actual caller `0x55496e` |
| Immediately before request 4 call | PC `0x554974`, R1=4, R4=−4, original SP/TCB retained |
| Second request/trigger | ID 4, cumulative requests 2/triggers 2 |
| Second wait | 66,808 iterations, cumulative busy 266,808 |
| Stop cause | Watchdog reset-request timer callback |
| Request 4 return, cleanup, setter return | Not observed |
| Normal calculation and derived RAM generation | 0 |

The subsequent interval was 3.282107 virtual seconds. Final mode word was 22, MIPS 167, and GAF state pending=true, request_id 4. Control history matched A272 clear → 2A enable → 73 trigger for both requests. Retained RAM reads/writes were also 0, with no model rejections.

Watchdog CFG `0x020ce005`, RSTGEN CFG 2, and WDREN=true were retained. reset_due, gating_evaluated, and allowed_by_gate were all true; restart count was 188, unchanged from the first return. The actual pause stack came from `BlackwallApollo510Watchdog`, with internal=false and aborted=false. All strict guards, CFSR/HFSR, and memory violations were 0. The stop PC is the execution location at the asynchronous event, not asserted to be the instruction causing the error.

This profile's WDT intentionally pauses after evaluating the request. **No actual reset/reboot was performed in this run.** The earlier [app return after watchdog](../power/watchdog-reset-restart.md) is a separate run and contract. The difference in absolute WDT observation time from the previous 10 MIPS failure run is 100 ns, within the current 167 MIPS report precision of 1 µs. Changing CPU execution rate did not extend the WDT clock. This does not verify the physical G2 timeout order or 14-second interval.

## Comparison and audit

The first timeout results before and after the one-shot change are exact except for host elapsed time. Existing complete core JSON and four SRAM snapshots (initial, connection, ATT, first return) are also exact. Original main, board, and device models are byte-exact; observation changes are limited to the owned stop's once condition and subsequent read-only observations.

Twenty-six saved audits and three counterexamples rejecting a fake setter return, missing second request, and disabled WDT passed. Inputs were regenerated and bytes and manifest values compared. Material is preserved outside Git in `gaf-after-timeout-native-01` and `gaf-after-timeout-research-01`.

## Next boundary for the overall goal

This pinned frozen-core failure scenario established first timeout → second request → watchdog request. Do not further expand timing/control variants of the same failure. Normal GAF calculation still requires a specification/code, exact ROM execution contract, or independent input/output expectations; automatic ready or zeroing unknown RAM is not a substitute. This failure path does not complete E05 initialization as a whole or E12 normal sample consumption.

The next work axes are an E16 shared tool combining existing candidates, scenarios, frames/events, stops, and comparison material in one run command, and independent evidence for normal sensor calculation. Also examine runner lifecycle within the existing runner to reduce the cost and duplication of repeating the same eight-minute prefix. Do not expand scope to user-feature CFW development or installer productization.

All 16 conditions, wording, and states remain at 8/16=50.0%. No real-device access, writes, subagents, or external publication occurred.
