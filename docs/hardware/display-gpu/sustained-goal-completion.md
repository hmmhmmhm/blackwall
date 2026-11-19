# Completion audit for six/60-second post-screen goal

2026-11-16. All ten original goal conditions completed. Twelve cold runs, six pairs, and three per-original six/60-second integrations were verified. This does not declare full chipset precision, ROM boot, or one-hour execution complete.

| Original | Actual virtual seconds after screen, six-second runs (two each) | Actual virtual seconds after screen, 60-second runs (two each) |
| --- | --- | --- |
| Stock 2.4 | 6.017903 / 6.011489 | 60.038764 / 60.011987 |
| Stock 2.3 | 6.005872 / 6.003891 | 60.017361 / 60.021926 |
| Faceclaw 38 | 6.001175 / 6.002039 | 60.010684 / 60.010816 |

## Original ten conditions and evidence

| Condition | Result | Canonical evidence |
| --- | --- | --- |
| 6-stock24 — two stock24 cold runs six seconds after first screen | Complete | private:simulator/sustained-final-audit-01/report.json |
| 6-stock23 — two stock23 cold runs six seconds after first screen | Complete | private:simulator/sustained-final-audit-01/report.json |
| 6-cfw — two cfw cold runs six seconds after first screen | Complete | private:simulator/sustained-final-audit-01/report.json |
| 60-stock24 — two stock24 cold runs 60 seconds after first screen | Complete | private:simulator/sustained-final-audit-01/report.json |
| 60-stock23 — two stock23 cold runs 60 seconds after first screen | Complete | private:simulator/sustained-final-audit-01/report.json |
| 60-cfw — two cfw cold runs 60 seconds after first screen | Complete | private:simulator/sustained-final-audit-01/report.json |
| cost — measured execution cost and failures/workload | Complete | private:simulator/sustained-final-audit-01/report.json |
| rom-gap — determine required ROM/initial-state material gaps | Complete | private:simulator/sustained-required-gaps-01/report.json |
| gpu-gap — determine required independent GPU ground-truth gaps | Complete | private:simulator/sustained-required-gaps-01/report.json |
| gaf-gap — determine required independent GAF calculation/output gaps | Complete | private:simulator/sustained-required-gaps-01/report.json |

## Scope of completion judgment

Full audit private `sustained-final-audit-01/report.json` has passed/full_goal_verified=true; all 12 rows, six pairs, and three integrations passed. It verified pinned hash list for 1932 file references, original main/SRAM, model/board/runtime insertion and host-guard selection, UI queue/TCB and DMA stream, virtual-time/instruction progress, and fault/guard 0. Actual times including overshoot of each duration target were recorded without concealment.

Sensor/GPU/RTC/power and controller identity during execution are declared functional profiles. Virtual controller identity is not presented as physical identification. Original ARM was not changed and PC/return/TCB were not forced. Startup PC and signals are bounded samples, not proof of every instant's full execution or all tasks/IRQs.

## Costs and failure

Total Docker wall for 12 final-profile successes is 8104.943 seconds (about 2.25 hours). One failure under same profile, 314.454 seconds, is preserved separately so errors are not hidden from a 13-attempt view. Seven existing successes were reused and remaining five run with a new manager. Resume manager resource-collection errors were 0. [Detailed cost and measurement scope](sustained-execution-costs.md).

## Required-material gaps

Exact Apollo510B Boot ROM/Info1 and security initial state, independent GPU pixel rules/output, and GAF EDMP computation/ISA or independent numerical input/output reference are lacking. Report reverified hashes of 15 actually held assets and distinguished each gap/acquisition path. Completion of gap determination is not counted as precise implementation completion. [Detailed gaps](sustained-required-material-gaps.md).

## Rejection verification, lifetime, and cleanup

Ten prior six-second rejection counterexamples and seven new integrated mutation counterexamples were reviewed. The latter rejected advertising phase/status, physical identity claims, unreviewed host limit, runtime mutation, reduced duration, and UART hash mutation. Original capture SHAs confirmed unchanged. Final execution/audit 17 and record 17 unique unit checks passed. Evidence logs preserved in private `sustained-final-review-bw521-01`.

All owned containers of 12 final completed captures were absent; both work managers and last child terminated. No physical access, flash/OTA, persistent writes, Astra, or external publication. Cleanup record for 507 reproducible caches/6510546 logical bytes and unchanged-source check for 796 files preserved. Subsequent tools/tests use `-B`/bytecode disabled; disposable Docker files removed with containers. Major analysis, inputs, commands, and verification results retained.

Follow-up proposal for 25 full-precision conditions remains inactive. This completion is not expanded to ROM cold boot, precise fusion/GPU, or physical safety certification.

Canonical SHA256: `587e29c71d293d31dda6168c5ee8736e0cb41bc85d6795af2d2ff2b1e4245cdb`.
