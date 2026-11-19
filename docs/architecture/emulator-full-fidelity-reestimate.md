# Re-estimate for Full Boot, Long Duration, and Fidelity Goal

2026-11-15, bw497 draft, reflecting latest repeated 60-second evidence. This is a **proposal** requested by the user. It does not change the active Goal, budget, or completion rate. No Astra, new native execution, physical access, or external publication occurred.

## Gap between current evidence and objective

A functional path exists from original main reset to display, along with two six-second post-screen runs each for stock 2.4, 2.3, and Faceclaw 38. These are evidence under declared virtual-device profiles. They do not establish actual Boot ROM execution, continuous ROM → bootloader → main boot, long-term stability, or physical accuracy.

Original stock 2.4 passed 60.038764 and 60.011987 virtual seconds after first screen in two cold runs under a new functional profile. Both runs matched configuration and final frame, and original UI queue/TCB and UART DMA bytes were independently audited. This is the particular no-input, normal-idle-focused scenario; do not extend it to mixed inputs, long duration, or accuracy validation. Other originals and new six-second integration regressions were in progress.

Evidence: [repeated 60-second measurements](../hardware/display-gpu/sustained-first-sixty-second-results.md), [required-material gaps](../hardware/display-gpu/sustained-required-material-gaps.md), and [current progress](../hardware/display-gpu/sustained-screen-dashboard.md). The active subgoal was 7/10, not 70% of the complete fidelity objective.

## Recommended scope

Target **paths actually used by G2 firmware** under a pinned hardware profile for one G2 temple. Include actual Boot ROM → original bootloader → original main → display, comparison of three originals and CFW candidates, long-duration input/communication/storage/reset, and GPU pixels, sensor fusion, and peripheral behavior against independent references.

Requiring every instruction and peripheral combination of the entire chip, cycle accuracy, power/RF/analog, and simultaneous original execution of both temples and case is a separate project; the estimates below do not apply. Even on used paths, do not fill unavailable material with success stubs or substitute AHRS and declare accuracy complete.

## Remaining development effort

These are planning estimates for analysis, modification, diagnostics, verification, and records in a single Codex workflow, not measured work speed or delivery promises. Pure computation wait for long regressions and external material wait are separate; parallel agents are not assumed.

| Work package | Completion deliverable | Estimated remaining work |
| --- | --- | ---: |
| Scope/material/cost | Support list and fidelity contracts, new-profile evidence audit, cost re-estimate | 2–6 hours |
| 60-second integration stabilization | Reuse stock24 repeats, resolve other-original/subsequent periodic boundaries, run three originals twice each at 6/60 seconds on new integrated profile | 6–20 hours |
| 10 minutes → 1 hour | Repeated input, sensors, disconnect/reconnect, storage, resource trends, bounded observation, failure reproduction | 12–36 hours |
| Original bootloader execution | Connect initial state, ROM calls, validation, MRAM, IRQ/handoff to main/UI | 24–60 hours |
| Actual Boot ROM execution | After obtaining exact ROM/initial state, connect reset, aliases, security/validation effects | 24–80 hours |
| GPU fidelity | Actual used commands/format/blend/clip/sampling/packing corpus and independent pixel comparison, DMA/cache/IRQ | 32–80 hours |
| GAF sensor-fusion fidelity | Algorithm/EDMP path, calibration/time/quat/bias/accuracy/drift compared with independent time series | 40–120 hours |
| Peripheral fidelity | Used MMIO state machines, timer/power/retention, bus/DMA/FIFO/IRQ/storage errors and communication timing | 24–64 hours |
| Final integration | ROM start → long mixed scenarios, stock/CFW comparison, reproduction in another environment, full audit | 12–32 hours |

Total **176–498 hours**, planned as **about 170–500 hours**. At eight development hours per day, five days per week, that is about 4.4–12.5 working weeks, rounded to **5–13 working weeks plus computation/material wait**. This estimates remaining scope while reusing existing sources, harnesses, and six-second evidence; do not add past total hours again. Record overlapping package work under one owner; final integration handles cross-scenario verification only. Confidence for first-time ROM/GAF work is very low. If a new unsupported boundary appears, record why the scope changed and re-estimate.

Conditions for which materials are never obtained may remain incomplete indefinitely. First determine availability of ROM image/Info1/security initial state, exact GPU IP rules/independent output, and GAF algorithm/EDMP/independent numeric outputs. If physical reading or purchase of new equipment/material becomes necessary, propose the specific work separately.

## Computation-wait budget

The latest two stock24 cold runs cost 978.6361402 wall seconds for 60.038764 virtual seconds and 1193.5893057 wall seconds for 60.011987 virtual seconds after display: **about 16.3–19.9 wall seconds per virtual second (n=2)**. Each confirmed the same configuration/final frame and zero errors. Host load was uncontrolled, so this is an execution-cost range including observation/storage, not a speed regression, performance ceiling, or specific bottleneck assessment. The first run's total Docker lifetime of 1118.1659514 seconds includes compilation, cold boot, and termination.

| Scenario | Total virtual time | Sequential computation wait assuming the same ratio |
| --- | ---: | ---: |
| 60 seconds × three originals × two runs, full matrix | 6 minutes | About 1.6–2.0 hours |
| 10 minutes × stock24/registered CFW, two types × three seeds | 1 hour | About 16–20 hours |
| 1 hour × three originals × three seeds | 9 hours | About 147–179 hours (6.1–7.5 days of continuous computation) |

The first row includes the two already completed runs and is not a prediction of remaining time. The table extrapolates current stock24 normal-idle-focused cost to other originals/mixed workloads for planning. It excludes unsupported boundaries, cold compilation/boot, reruns, and root-cause analysis. Actual mixed input and sensor/GPU load may take longer. Preserve the earlier six-second six-run 14.0–16.4× figures as previous-profile history; do not mix them into the latest estimate's basis.

Docker used one CPU and 512 MiB; among 65 samples over the first 60-second run's full lifetime, maximum observed memory was 491 MiB. This is not a guaranteed peak or proof of no leak over time. Samples near one CPU core do not alone establish the bottleneck. After 10 minutes, check workload-specific cost/resource trends and profiler data before re-estimating the one-hour budget. Apply reduced observation, host batching, or warm supplementary tests from the same cold boot only when error detection and timing meaning are compared and preserved. Do not replace formal cold runs with warm snapshots or speed them up by skipping guest branches/checks. Do not double-count time when sequential computation overlaps development in calendar estimates.

## Proposed Goal and progress

> Under a pinned one-temple G2 profile, continuously execute actual Boot ROM → original bootloader → original main → 576×288 display without bypassing verification. Compare stock 2.4/2.3/Faceclaw and registered CFW candidates under repeated input, communication, sensor, storage, and reset scenarios, and verify one virtual hour of stable execution for three originals × three seeds. Validate GPU, GAF sensor fusion, and peripheral paths used by firmware against independent material/output and predeclared error tolerances. Unavailable material and substitute functional models do not count as fidelity completion.

Reusing the existing [25-condition proposal](../data/emulator-fidelity-scope-proposal.json) is recommended: boot 30, stability 25, GPU 15, fusion 15, peripherals 15 points; five conditions per area. Weights indicate importance, not time shares. Add points only for conditions passing evidence audit; **all 25 conditions** must pass for 100%. Do not remove blocked areas from the denominator. Retain existing v3 16/16 and current 7/10 as history of their respective scopes. After approval, map/audit existing evidence against new conditions before showing a first score; do not invent an initial completion rate.

Recommended order: **60-second integration → 10 minutes → one-hour stability expansion**, while assessing availability of ROM and independent reference results; **bootloader → actual ROM integration**; GPU/GAF/peripheral refinement; final integrated regression starting from ROM. This document proposes Goal setup and did not replace the active Goal.

## Activation proposal and first execution units

All 25 conditions remain proposed. If approved, pin the new scope and audit existing evidence condition by condition to calculate the first score. Do not transfer current 7/10 or historical 16/16 directly into the new numerator. In particular, current 60-second idle tests alone do not complete S03, which requires repeated input/sensors/disconnects.

Recommended units: (1) finish the ongoing six/60-second final matrix, (2) assess material availability/path and the 10-minute mixed scenario/cost, (3) continuous bootloader execution and expansion to one hour, (4) actual ROM integration and GPU/GAF/peripheral refinement, (5) integrated audit starting from ROM. First impose a four-to-eight-hour development research cap on material availability; if unavailable, record exact required inputs and resumption conditions. These four to eight hours are within the existing scope/boot/fidelity packages, not added to the total. Distinguish completing material research from completing implementation.

The 170–500 development hours are a low-confidence initial range for one workflow. Development alone is 5–13 working weeks; at current speed, a major long regression set may need another 6–8 days of sequential computation. These periods may overlap, so no completion date is promised by simply adding them. Waiting for ROM/GAF/GPU reference assets is separate; if they cannot be obtained, an overall completion date cannot be set. The estimate does not apply to full-silicon, all-IP, cycle/power/RF accuracy.
