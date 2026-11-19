# Virtual PMIC VBAT/IBAT Conversion and Result Bits

bw-0147. An optional digital conversion model was connected without changing actual original ARM.

## Evidence and declared scenario

The [official single-measurement contract](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/saadc/doc/frontpage.html-ad-hoc?contentId=7~JUnGOOdtmgX05h6AnYPg), [VBAT/IBAT linkage](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/saadc/doc/frontpage.html-unique_1005789508?contentId=P6pFPApdUp3g~OtFNEbH5w), and [result layout](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/saadc/doc/frontpage.html-results?contentId=kBmX07pcdP9Iuvu7ScOWYQ) were checked. System Monitor electrical specifications in [official PS v1.0](https://docs-be.nordicsemi.com/bundle/nPM1300_PS_v1.0/raw/resource/enus/nPM1300_PS_v1.0.pdf) give a typical 250 µs conversion time. This is not measured G2 timing or latest-silicon verification. Addresses, masks, and event bits were compared with pinned npmx ADC/ADK files.

Selected profile `discharging-vbat-ibat-fixture` specifies raw 10-bit VBAT 778/IBAT 5. Its two stages—VBAT 250 µs then optional IBAT 250 µs—are declared virtual timing, not verified physical scheduling/delays. Status 4 is a fixture declared discharging/valid. Source-reset ADC configuration and existing scratch0 mock 0, INFO1/revision/power/cache assumptions remain.

| Item | Output | Known scope |
| --- | --- | --- |
| VBAT complete | 0511=c2, 0515 bits 1:0=2 | Split of sample 778 |
| IBAT complete | 0518=01, 051a bits 5:4=1 | Split of sample 5 |
| IBAT status | 0510=04 | Fixed discharge/valid fixture |
| Completion event | VBAT 01, IBAT 40 | MAIN event bank 0 latch |

Other channel bits in shared LSBs are unknown by default. Unsupported sibling bits are 0 only when `sharedResultBitsZeroMock=0` is separately explicit; measurement bits remain unknown until completion. Other channel MSBs are not supplied. Value and known mask are reported together to distinguish internal value 0 from known 0.

## State and error contract

An actual Renode LimitTimer is used rather than emulating events with a host-reimplemented clock. Root's typed ADC backend connects task 500 and result range. Omitting the profile retains the existing strict 500 boundary. Supported mode is manual single-shot cfg0. Repeated requests during VBAT are dropped without restarting the clock. Queuing a new VBAT request during IBAT and other tasks such as NTC are unimplemented and rejected. ADC configuration and 050c task writes during conversion are rejected in preflight, preserving settings, counts, and history. Enabling auto/burst while idle is also blocked. Results persist until the next completed conversion or Reset; events persist until guest clear or Reset.

Reset cancels the timer and returns to the declared fixture as model initialization, not physical PMIC reset. Logical DigitalIrqPending differs from actual GPIO/NVIC delivery; the latter is not wired.

## Unit verification and time-input correction

Private `pmic-adc-conversion-unit-05` passed 408 checks: existing 369 and 39 new. They cover 249/250 µs and 499/500 µs boundaries, raw 0/1023 packing, event latch/guest clear, repeated requests and unsupported queue, blocking reads before measurement/of unsupported channels/unknown LSB, atomic configuration-change rejection during conversion, and Reset cancellation.

unit01 failed before compilation due to missing IPeripheral declaration on the timer owner. 02/03 failed boundary checks because the string 249 µs + 1 µs time produced tick 249. In 04, integer TimeInterval.FromMicroseconds passed 405 checks; 05 added exact elapsed 250000/500000 ns, IBAT configuration blocking, and time-input comparisons. Actual string 249 µs advance was observed as 248999 ns, versus 249000 ns with integer API. Timer limit was unchanged. This is an observation of test time-input paths, not physical PMIC error or performance. Independent review's in-progress configuration issue was addressed with typed preflight and rejection tests for both phases.

## Original ARM integration result

`pmic-adc-conversion-main-01` completed three originals plus two controls, five cases total. All three originals stopped at NTC 501 write (width 3) while IBAT was in progress, after one virtual VBAT completion and latched event 01. Original ADC interrupt enable is 0 and DigitalIrqPending=false; IRQ was not forced. IBAT completion/event 40 has not yet been observed in original runs; it was confirmed only in unit tests. Original code did not read results 0510..051a before stopping. This is not evidence that raw 778/5 were consumed or calculated by the original.

The control with measurement model disabled retained the existing 500 boundary. Stock 2.4 control without shared-zero reached the same 501 boundary even with mask515=03. Both stock 2.4 inputs are identical except the board's one sharedResultBitsZeroMock line. Comparison is limited to the prefix before result reads and does not establish equivalence of later behavior or actual initial state.

## Final audit and remaining scope

The 115 checks in `pmic-adc-conversion-verification-01/report.json` compared source snapshot, raw/unit 408/main 5, exact phase/value/known mask, VBAT task/next NTC rejection, event-versus-IRQ distinction, no result reads, default boundary preservation, pinned main invariance, identical 2.3/CFW models, shared-mock condition differences, time-input comparison, and upstream pins. `pmic-timed-unit-10` 240 checks and `recovery-pmic-feed-11` five ARM cases were also reverified. The latter retains explicit power/pins/frozenDWT/status-hole mocks. No transcript archive comparison occurred. Independent GPT-6-family review's original/unit-test interpretation scope was incorporated.

Next are NTC/die/VSYS, request priority and queue, and grouped/fragmented result-read contracts. Current one-byte result-read verification is not generalized to passing all SDK all-results/IOM chunks. Full ADC, full boot, app loop, display, and physical installation/recovery remain incomplete. Product completion remains 13/29.
