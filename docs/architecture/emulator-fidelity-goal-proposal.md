# Proposal to Expand G2 Emulator Fidelity Goal

bw491. **This is a proposal for review; no new Goal or scope v4 was activated.** Existing v3 16/16 is retained as history of completed pinned functional tests. Do not carry that number into completion of this proposal's ROM/long-duration/fidelity scope. No authorization for physical access, installation, Astra, or external publication was added.

## Starting point at the time

There are original main reset → services → RTOS → 576×288 UI and some input/sensor scenarios. Post-screen lifetime is mainly 100 virtual ms. Stock24's reset → first screen was 8.621994 virtual seconds, but **this does not mean the screen remained displayed for 8.6 seconds**. Six-second, 60-second, 10-minute, and one-hour lifetime validation are new conditions.

`run_post_screen_lifecycle.py` is limited to 100 ms, 32 frames, and 180 host seconds. Merely increasing time may fail to validate properly because of sample limits, saving all frames, observer overflow, and new periodic work. Finite buffers, summaries, periodic snapshots, and progress assessment for long observation are needed first.

Original bootloaders 2.3.2.14/2.4.0.24 and function analyses exist. MRAM binding calls ROM entry 0x0200FF21, while prior tests mocked ROM returns. Continuous original Boot ROM reset → bootloader → main execution has not been proven. This investigation did not newly obtain a verified exact complete G2 ROM image or initial security/Info1 state. Having a bootloader image does not mean Boot ROM is available.

The GPU handles original command lists, but some coverage, sampling, and packing rules are functional reference policies. Half-pixel bit meanings differ between other Nema IP-generation documentation and Apollo headers, requiring an independent reference. For sensors, distinguish FIFO/IRQ and original host decoder/axis conversion verification from internal GAF fusion. Of 46 relevant drivers in the user-supplied SDK, 45 matched the existing public copy after LF normalization; the other differed in version string. There is no evidence that complete GAF calculation code, EDMP ISA, or numerical ground truth was obtained.

Existing evidence: [main boot](../firmware/native-main-boot-acceptance.md), [final v3 audit](emulator-final-audit.md), [boot analysis](../bootloader/bootloader-2-4-analysis.md), [unknown GPU rules](../hardware/display-gpu/gpu-sampling-source-boundaries.md), [actual SDK source review](../research/icm45608-sdk-source-review.md), and [sensor consumption](../hardware/sensors-input/sensor-task-consumption.md).

## Scope options

1. **Increase reproduction fidelity for paths used by G2 — recommended.** Verify continuous ROM/boot, long duration, and actually used GPU/sensor/peripheral behavior for one temple, three pinned originals, and an independent CFW candidate. Leave unavailable ROM/reference material incomplete. The goal is agreement with independent references for these paths; it excludes power, RF, analog, and all-ISA/cycle accuracy.
2. First complete only long-duration functional tests. This is immediately useful for development and relatively easier to estimate, but does not satisfy the user's complete fidelity objective. Use it as a first step without narrowing the overall goal to it.
3. Match all silicon, all IP, cycles, power, and RF. Available material and assets do not allow a completion-date estimate. This is separate research beyond Renode board functional-model expansion, and even a months-long schedule cannot be guaranteed.

## Work breakdown and estimated effort

The times below are **initial planning ranges of development effort for analysis, changes, short diagnostics, failure investigation, and evidence audits in one Codex workflow**. They are not measured throughput or a completion promise. Pure computation wait for long regressions, external material/permission/equipment wait, user absence, and service interruptions are separate. No acceleration from parallel agents is assumed.

| Package | Actual work and outcome | Planned time | Confidence / prerequisites |
| --- | --- | ---: | --- |
| W0 scope and execution cost | Pin fidelity grades/25 conditions, list ROM/oracle assets, measure wall time/CPU/memory per virtual second | 3–6 h | Medium. Long-duration speed not yet measured |
| W1 6/60 seconds | Bounded observation, state/display/IRQ/task progress, two cold runs per original and same-seed reproduction | 6–16 h | Below medium. New periodic tasks may hit unsupported boundaries |
| W2 10 minutes/1 hour | Stock24 10-minute mixed inputs, then three originals for one hour, three pinned seeds, sparse frames/periodic state and intermediate-failure reproduction | 12–36 h | Low. Depends on throughput, timer/log accumulation, new device boundaries |
| W3 original bootloader | Load/vector and initial state, ROM-call inventory, IRQ/ITCM/MRAM/verification path, connect stock bootloader reset → main → display | 24–60 h | Low. ROM API functional model is intermediate, not completed actual ROM execution |
| W4 actual Boot ROM | After exact ROM/provenance, connect CPU reset, memory aliases, security/Info1, verification engine → original bootloader → main | 24–80 h | Very low. **Start/completion dates cannot be estimated without required ROM/initial state** |
| W5 GPU | Used command/shader corpus, independent pixel oracle for format/blend/clip/coverage/sampling/packing, DMA/cache/IRQ/reset order and rejection, three-original regression | 32–80 h | Low. Exact IP evidence/independent actual output first |
| W6 GAF fusion | Initialization/calibration, motion time series, quat/bias/accuracy/timestamp, numerical implementation or EDMP execution, reset/calibration/drift controls | 40–120 h | Very low. **Independent algorithm/actual input-output material unavailable. Substitute AHRS is not completed GAF equivalence** |
| W7 peripherals | State-machine/fidelity inventory for used MMIO, timer/power/cache/retention, IOM/SPI/UART/DMA/FIFO/IRQ/storage failures, actual startup-peer protocol/timing evidence | 24–64 h | Low. Keep items without physical reference as functional models |
| W8 integration/regression | Connect input/fusion/GPU to long ROM-start scenario; candidate/stock comparison, automatic reports, missing/error detection, new-environment reproduction | 12–32 h | Low. Requires independent evidence from prior packages |

Total: **177–494 h, planned as about 180–500 h of development + long computation wait + unavailable-material wait**. At eight effective development hours per day and five days per week, development alone is about 5–13 working weeks; this is not an overall completion date. Do not assume running continuously for 24 hours simply reduces the schedule to one third. If material is never obtained, additional time may not complete the overall fidelity goal.

Compute long-run budget separately as `virtual execution time × measured wall/virtual ratio × number of runs`. For example, three originals × three seeds × one virtual hour is at least nine virtual hours. At ratio 10 that is 90 real hours; at 100 it is 900. **These ratios are examples, not current measurements.** Because sleep fast-forward and active UI/IRQ workloads differ, W0 measures idle, display updates, and sensor load separately and records actual bottlenecks among CPU/log/GPU and completed work. If disabling observation improves speed, separately verify equivalent failure detection and artifacts. Distinguish computation wait in work records to avoid double-counting it as development time.

The estimate is engineering judgment based on the number of packages for finding and fixing new boundaries. Recent bw478–490 start-to-finish totals were about 6.53 hours, but those were small integration tasks reusing existing research and not measured focused time. That speed was not linearly applied to ROM reverse engineering. Past total Goal elapsed time was not used as a proxy for task throughput. Evidence, timestamps, and source SHA are retained in private `simulator/fidelity-goal-proposal-bw491/evidence.json`.

## Recommended sequence and first Goal

**Perform W0 → W1 first, then increase W2 in stages.** Stabilize the development foundation where the display remains visible. Conduct W3 in an order that exposes exact ROM-call and material gaps. First determine availability for W4/W5/W6; do not pass by repeatedly searching the same public sources or assuming success flags. Do not stop independent long-duration/GPU material organization merely because ROM is unavailable.

First Goal proposal (initial planned development effort 12–24 h plus computation wait calculated after measurement, not an automatically set execution budget):

> Preserve existing original ARM and strict/functional models while verifying continuous post-screen execution for six and 60 seconds twice for each of three originals, and machine-assess progress of virtual time, tasks/IRQ, UI, memory/queues, and errors. Confirm same-seed reproducibility and intentional fault detection. In parallel, determine availability and acquisition paths for Boot ROM/initial state, GPU pixel oracle, and GAF numerical references, then re-estimate feasibility and effort for the next phase. Leave unsupported behavior as failure/unknown; do not force CPU branches/returns/TCB or success states.

The first Goal is intended to obtain measurements and a defect list. First complete W0's 3–6 h investigation/measurement and calculate actual execution wait for the six/60-second matrix. This is not a promise to complete ROM/GPU/GAF fidelity or the entire first Goal in 12–24 calendar hours. If new long tests reveal problems, record first causes and re-estimate scope.

## Draft overall Goal and completion rate

Draft overall Goal:

> Under a pinned one-temple G2 profile, continuously execute actual Boot ROM → original bootloader → original main → UI without branch or verification bypasses. Reproduce long-duration input/communication/storage scenarios for stock 2.4/2.3/Faceclaw and registered CFW candidates, and compare GPU, sensor-fusion, and peripheral paths used by G2 against independent original material/output and predeclared error tolerances. Unavailable ROM, private calculations, and unverified device behavior do not count toward completion. Cycle/power/RF/optical accuracy, full original execution of both sides/case, and physical installation certification are separate scopes.

The scope draft has 25 conditions in `emulator-fidelity-scope-proposal.json`: boot 30 points, long duration 25, GPU 15, fusion 15, peripherals 15, totaling 100. These are fixed goal weights, not effort estimates. Each area has five equally weighted conditions. All conditions must pass for overall completion. Obtaining Boot ROM alone does not complete boot, and retesting raw FIFO in place of fusion cannot earn fusion points.

Mark reusable existing evidence separately, but do not automatically carry it forward as completion of new conditions. The first display is **0/25 verified under newly approved criteria (not evaluated)**, which does not mean rebuilding the project from scratch. Freeze the pinned scope, supported feature list, independent corpus, tolerances, and scenarios together on approval. Do not inflate denominator/numerator by later adding tiny checks. Material blockers leave the relevant condition unknown/blocked and cannot be erased by completion of other conditions.

## Fidelity evidence and stop criteria

ROM requires exact silicon/revision, image SHA, reset entry, license/provenance, and security/Info1 profile. An SDK boot description or ROM API stub alone does not establish actual ROM boot completion. Investigate public/permitted material first; physical reading, development-board purchase, dumping, security changes, and persistent writes each require separate assessment within the necessary authorization scope.

For GPU, freeze actual G2-used commands and inputs distinguishing asymmetric nibbles, half pixels, nonzero destination, clipping, boundaries, and quantization. Do not validate a mathematical model with an image produced by that same model. If only specification agreement is demonstrated without a physical oracle, label that level and leave physical matching incomplete.

Do not complete fusion based only on stationary quaternion. Compare quat/bias/accuracy/units/timestamps and drift across a pinned corpus including rest, rotation, acceleration, magnetic disturbance, sensor dropout, and calibration/reset. Pin tolerances before testing after checking source precision and repeatability error. Do not invent an angle-error ground truth before obtaining actual GAF results.

Long-duration tests do not pass solely because CPU instruction counts increase. Check input responses, relevant tasks/queues, IRQ clearing, time progress, screen updates/normal idle, host/guest resource trends, and model errors. Do not force unnecessary screen updates in idle. Separate warm-snapshot-only tests as supplementary and preserve each cold run's reset lineage. Distinguish virtual time and wall time even when the original sleeps.

Re-estimate first after W0–W1, second after the 10-minute test, and whenever ROM/oracle availability changes. Do not repeatedly claim “a few more hours” without evidence for unavailable material. Maintain existing task keys, input fingerprints, and append-only work log for status and duplicate prevention.

## External primary sources checked

- [Ambiq Apollo510 datasheet 1.1.0](https://contentportal.ambiq.com/documents/20123/2877485/Apollo510-SoC-Datasheet.pdf/6f7b4ae1-6630-d80c-1e17-ec7445b0509e?download=true&t=1780184793760): evidence of Boot ROM, OTP/security, and GPU existence. Do not extend it to exact G2 Apollo510B ROM bytes or all internal algorithms.
- [Official TDK ICM45608 driver](https://github.com/tdk-invn-oss/motion.arduino.ICM45608): provides GAF initialization and FIFO quaternion-output APIs. Their existence does not mean fusion algorithm source is available.
- [Renode testing documentation](https://renode.readthedocs.io/en/latest/introduction/testing.html): can support repeated testing and preservation of failure states; does not guarantee long-duration passes or G2 support.
- [JohnRThomas/even_realities_decomp](https://github.com/JohnRThomas/even_realities_decomp): its current README identifies G1/nRF5340. Do not count it as a substitute source for G2/Apollo510B ROM or GPU accuracy.

This work reviewed records, source, and primary sources and wrote a proposal. No new long-duration ARM execution, speed benchmark, ROM acquisition, physical-device access, or Goal change occurred.
