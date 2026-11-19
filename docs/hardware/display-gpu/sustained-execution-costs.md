# Post-screen execution costs and measurement scope

Final report. Three originals × six/60 seconds × two cold runs, 12 total, six pairs and integrated verification of three originals completed. One failed attempt under the same final profile is reported separately. These are measured costs, not performance rankings, device FPS, or arbitrary-workload throughput.

## Actual costs of 12 successful runs

| Original/virtual period/run | Actual virtual seconds | Post-screen wall seconds | Total Docker wall seconds | Wall/virtual second | Original instruction increase | Frame increase | Maximum observed MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| stock24 60s #1 | 60.038764 | 978.636 | 1118.166 | 16.300 | 1,151,115,163 | 10 | 491.0 |
| stock24 60s #2 | 60.011987 | 1193.589 | 1352.247 | 19.889 | 1,150,721,424 | 10 | 497.9 |
| stock23 60s #1 | 60.017361 | 827.722 | 914.567 | 13.791 | 1,106,902,674 | 10 | 508.3 |
| stock23 60s #2 | 60.021926 | 800.970 | 888.289 | 13.345 | 1,107,029,630 | 10 | 511.9 |
| cfw 60s #1 | 60.010684 | 1019.139 | 1132.134 | 16.983 | 1,150,340,252 | 10 | 510.0 |
| cfw 60s #2 | 60.010816 | 1068.444 | 1164.317 | 17.804 | 1,150,362,323 | 10 | 498.4 |
| stock24 6s #1 | 6.017903 | 140.833 | 285.088 | 23.402 | 130,612,549 | 10 | 503.6 |
| stock24 6s #2 | 6.011489 | 158.196 | 374.185 | 26.316 | 130,436,018 | 10 | 511.9 |
| stock23 6s #1 | 6.005872 | 171.241 | 308.677 | 28.512 | 125,055,105 | 10 | 512.0 |
| stock23 6s #2 | 6.003891 | 101.486 | 215.343 | 16.903 | 125,041,578 | 10 | 511.9 |
| cfw 6s #1 | 6.001175 | 94.130 | 182.730 | 15.685 | 129,564,885 | 10 | 502.3 |
| cfw 6s #2 | 6.002039 | 86.317 | 169.200 | 14.381 | 129,551,235 | 10 | 511.8 |

## Wall seconds ÷ virtual seconds by original/period (n=2)

| Original/period | Minimum | Median | Maximum |
| --- | ---: | ---: | ---: |
| stock24-6000 | 23.402 | 24.859 | 26.316 |
| stock23-6000 | 16.903 | 22.708 | 28.512 |
| cfw-6000 | 14.381 | 15.033 | 15.685 |
| stock24-60000 | 16.300 | 18.095 | 19.889 |
| stock23-60000 | 13.345 | 13.568 | 13.791 |
| cfw-60000 | 16.983 | 17.393 | 17.804 |

Total Docker wall for 12 successes is 8104.943 seconds (about 2.25 hours). Including the one failure below it is 8419.397 seconds (about 2.34 hours). This is the sum of sequential execution intervals for 13 final-profile attempts, not total project time including source analysis, tool development, earlier-profile diagnosis, waiting, and research.

## Measurement interval and evidence of work

- Post-screen wall starts Stopwatch at the first complete-frame stop boundary and includes initial frame/SRAM recording, resume/periodic pauses/sample storage, and final pause/sample. Detailed fault/export and subsequent Python audit follow. Virtual time is difference in before/after machine ticks, including actual overshoot in the table.
- Total Docker wall measures execute call after derive using a monotonic clock. It includes compile, cold boot, post-screen execution, termination, and owned-container cleanup; input derive and subsequent audit are excluded. Host management waits during execute are included.
- Original virtual time and CPU instruction increase, final-frame match in each pair, original UI queue/TCB receive wait, UART original DMA bytes/FNV, and zero errors were independently verified. Tests that merely passed time or failed early were not calculated as successful cost.
- Docker used pinned image, CPU 1, memory 512 MiB, pids 128, network none. Each run had 10–81 resource samples. Worker's approximately 15-second docker stats intervals lengthen with execution duration and include compile/cold boot. Maximum observed is neither peak nor per-process usage.
- Host concurrent load was uncontrolled and no profiler was enabled. CPU samples alone do not establish a specific code/resource bottleneck, and samples over 100% are not calculated as quota-violation evidence. Maximum memory sample 512.0 MiB does not guarantee absence of long-term leaks or headroom.
- This is an n=2 execution-cost range, not performance ranking/regression comparison. In particular do not linearly apply six-second initialization, fade, and periodic-save costs to 60 seconds or one hour. Physical behavior, every frame/IRQ, and arbitrary mixed input are outside verification.

## Failed attempt and resumption

One stock24-6s-r2 attempt under the same final profile stopped at the first detail-frame host 90-second limit. It advanced only virtual 45.294 ms and had no detailed frame/six-second telemetry, so remains a failure. Total Docker wall was 314.453771875 seconds. A separate docker stats 15-second TimeoutExpired terminating the manager is recorded distinctly. Container/manager/children were confirmed stopped and preserved as-is.

A helper recording resource-sampling errors as failed samples (exit 124) while continuing to wait for native child termination was verified in three checks. The resume manager reused seven existing successes and ran only the remaining five. Final original/model/runtime/budget SHAs were unchanged; resource collection errors were 0 in the five resumed runs. Earlier failure data were not changed to success.

Earlier 100 ms pilot and MSPI, RTC, UART, HCI, and first-render 30-second-limit diagnoses are separate profile history. Evidence is preserved in [plan](sustained-screen-plan.md), [RTC](sustained-rtc-write-lifecycle.md), [UART](sustained-uart-history.md), and [HCI](sustained-hci-advertising-stop.md), not mixed with the 13-attempt statistics above.

## Use in long-run planning

Wall/virtual second for six final 60-second runs is approximately 13.345–19.889. Assuming the same ratio, three originals × three seeds × one virtual hour (nine virtual hours total) would take about 120–179 actual hours, but this is a planning extrapolation. Ten-minute/one-hour runs, mixed input/sensor load, log accumulation, and new device boundaries were not tested, so it cannot guarantee delivery time or stability. Remeasure workload-specific cost and resource trends in the next ten-minute test.

## Evidence

Canonical private: `simulator/sustained-final-audit-01/report.json`

SHA256: `587e29c71d293d31dda6168c5ee8736e0cb41bc85d6795af2d2ff2b1e4245cdb`

Report files pin frozen source, 12 captures, original UI/DMA, resource samples, and 15 material assets. `passed/full_goal_verified=true` applies to the post-screen six/60-second and material-gap determination scope. [Final report](sustained-goal-completion.md).
