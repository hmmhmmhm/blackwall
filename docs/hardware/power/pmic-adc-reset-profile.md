# Explicit ADC Reset Configuration and Auto-Update Requests

bw-0146. This distinguishes a profile supplying source reset values from the existing unknown profile.

## Contract and scope

The ADK and adc.c from pinned npmx `4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f` were compared with the [PMIC ADC documentation](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/saadc/doc/frontpage.html?contentId=5owliBBpCrxzvTvnK6iS3A). source-reset-storage declares initial values `[00,01,03,00,00]` for configuration addresses `[0509,050a,050b,050d,0524]`. These were not read from current G2. Existing guest-storage keeps 050b/050d/0524 unknown until guest writes.

In the new profile, task 050c is a no-op for value 0; value 1 records the then-current 050b configuration and request count. State changes after validating bit mask and history. Measurement timers, interval application, automatic conversion, results, and completion events are not implemented. The SDK interval setter requests the task after 050b read-modify-write, and vbat-auto configuration is also preceded by update. Original trace is compared with this call pattern, without claiming the entire SDK C function is byte-identical to the original.

Reset() is test initialization of the declared profile, not verification of physical POR/soft reset or state retention. Previous scratch0InitialMock=0 and INFO1/revision/power/ADC/cache assumptions also remain.

## Unit tests and failure correction

`pmic-adc-reset-unit-02/report.json`: existing 344 plus 25 new checks, 369 passed. They check explicit initial values/readback, zero task, request snapshots, atomic invalid-value rejection, result/task read blocking, no events generated, fixture Reset, and existing strict guest profile. unit01 failed because loop variable state from the earlier SCRATCH test shadowed DRIVER's state() helper. Renaming it scratch_profile/scratch_fixture corrected the test connection; failure material was preserved. A subsequent invocation incorrectly passing an existing parent path as output was rejected before execution; that path was not changed.

## Original execution and records

Based on pinned pmic-scratch-main-01, only the ADC profile was changed for the three originals; stock 2.4 control retained guest-storage. All inherit scratch0 mock 0. Private `pmic-adc-reset-main-01` completed three originals plus one control. The three originals had ADC configuration addresses `[0509,050a,050b,050d,0524]`, values `[00,03,03,00,01]`, and four configuration writes. Recorded order was 050a=3 → 050b=3 → 050c=1 → 050b=3 → 050c=1 → 0524=1. Both 050b reads were also 3. This order shows two interval RMWs and task requests alongside current-measurement configuration. The next strict boundary is VBAT measurement task 0500 write (width 3). No result-register reads or ADC completion events have occurred. The existing-profile control retains one configuration write and zero update requests, stopping at 050b read (width 2). Watchdog timer was Start 0/running=false in all originals.

## Metadata correction and final audit

Existing derived-inputs.json recorded storage as guest-storage when enabled and null in control. Interpreting this field as the actual ADC profile would be wrong. Board/runtime at execution are authoritative; final `pmic-adc-reset-verification-01/actual-profiles.json` corrects the record to source-reset-storage for three originals and guest-storage for control while preserving original metadata and board hashes. Existing run files were not modified. Future runners record actual_adc_state from the actual board and correct the new profile's storage name. AST comparison verified the runner at execution and current runner differ only in two metadata fields. The same ARM execution was not repeated solely for this correction.

The 97 checks in `pmic-adc-reset-verification-01/report.json` compared raw/unit 369/main 4/source, pinned main invariance, exact configuration/request order, next VBAT block, control boundary, actual profile/metadata correction, and source pins. Stock 2.4 profile/control share eight execution inputs apart from the board's one ADC profile line. After constructor behavior changed, `pmic-timed-unit-09` 240 checks and `recovery-pmic-feed-10` five ARM cases were reverified. The latter retains explicit power/pins/frozenDWT/status-hole mock conditions. Independent GPT-6-family review's distinction between metadata and actual profile was incorporated. No transcript archive comparison occurred.

## Next implementation boundary

Remaining work is VBAT measurement value, conversion time, completion event, and its relationship to current measurement. Adding only a task counter does not establish successful conversion. First define an explicit virtual sensor scenario and source-based request/result/event order, then compare with original execution. Full ADC behavior, full boot, display, and real-device installation/recovery remain incomplete. Product progress remains 13/29.
