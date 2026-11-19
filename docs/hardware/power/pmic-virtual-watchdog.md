# Virtual PMIC Watchdog and Fragmented I2C Frames

bw-0141. Verified in a Renode model without physical-device access.

## Implementation scope

`tools/renode-pmic-timed-probe.cs` is an optional wrapper around the existing PMIC subset. It requires explicit `fast-reset-stopped`, assuming the initial timer is stopped. It supports only config 0x0a, stages a 24-bit target, and commits it by strobe. Fragmented transfer of a target frame up to five bytes is applied at STOP; invalid frames do not affect the target. It supplies start, stop, kick, and an independent virtual 500 Hz clock.

Warning latches an event one tick before target. Kick resets time but does not clear an existing event. Expiry records a reset request and stops emulation. Actual reset, power reapplication, and GPIO/NVIC wiring are not implemented. For original target 0x3c00, nominal warning/expiry times are 30.718/30.720 seconds, not physical measurements.

Repeated-START reads are supported only for timer pointers; other PMIC registers retain the STOP subset. Status/reserved bytes in recovery code's six-byte read are unsupported by default. Only tests separately specifying `recoveryReadHoleMock=0` fill both bytes with 0. This setting is not used in original main runs.

## Verification

The 237 checks in private `simulator/pmic-timed-unit-04/report.json` include existing PMIC 201 checks. They cover fragmented frames, strobe, initial state, invalid config/target, kick, warning latch/clear, nominal target time boundaries, and blocking target changes after a reset request. After STOP at 4 ms and another 20 ms of execution, warning/expiry cancellation is confirmed; 7/8/10 ms boundaries are then checked from restart. A regression also checks that the latest guard diagnostic appears even when Inner blocks after wrapper blocking. These tests directly call II2CPeripheral from host; they do not execute compiled recovery feed.

unit01→unit02 added nominal target timing; unit03 added post-reset target guard; unit04 reverified with latest guard diagnostics and STOP/restart regression. Existing results were not pointlessly repeated under identical conditions.

## Still unconfirmed

- Full integrated execution of compiled recovery manager, scheduler, errors/timeouts.
- Actual PMIC initial timer state and status byte, and coexistence with scheduler and prolonged reception.
- Physical warning/reset/power-cycle and recovery of both temples.
- Full boot from ROM, main loop, and integrated display.

All three original ARM inputs in private `simulator/pmic-timed-main-02` reached config=0x0a, target=0x3c00, strobe=1. Start/kick/warning/reset are all 0. Next strict boundary is PMIC write 0x0201 (width 3); PC is 0x58236c for stock 2.4 and 0x57b014 for stock 2.3/Faceclaw. Guard address=0x030d is previous pointer diagnostics; the currently rejected register is identified by value=0x0201. Default-model control retains existing 0x0705 boundary. No branch/return override was added to original main. Existing synthetic INFO1, revision, power, ADC, and other assumptions remain.

`tools/verify_pmic_timed_evidence.py` compared final source snapshot, native raw logs/reports, pinned file hashes, original main invariance, default boundary preservation, and identical 2.3/CFW run conditions in 42 checks. Independent GPT-6-family review confirmed corrections of two earlier findings. The parent performed final main02 audit. No transcript archive comparison occurred. Product completion retains all 29 conditions; unit-check counts are not converted into progress.

## bw-0142 fragmented-read strengthening

[Recovery feed integration](../../bootloader/recovery-pmic-feed-integration.md) confirmed actual IOM peer read splits 4+2. Only under explicit zero-hole mock, a six-byte snapshot is delivered as 4+2 and overreads rejected. Earlier unit04/main02 evidence remains a record verifying the model at that time, not evidence of current source identity. New unit05 passed 240 checks: existing 237 plus head/tail/overrun three.

Latest main03 also retained existing boundaries for three originals and default control. Saved audit02's 82 checks compare latest unit/main and compiled recovery feed06 together. Earlier audit01 is a record of its then-current source.
