Current final status: two six-second and two 60-second runs per original across three originals and full independent audit complete (10/10). Below is intermediate history from first success. [Final report](sustained-goal-completion.md).

# First original 60-second run results

bw504–506. **One cold main run of original stock 2.4 ARM passed 60.038764 seconds after first screen.** Full verification of two runs each at six/60 seconds across three originals was not yet complete. This is a declared virtual board profile, not Boot ROM execution or physical accuracy certification.

| Item | Actual saved result |
| --- | --- |
| Virtual time after screen | 60.038764 seconds |
| Host wall after screen | 978.6361402 seconds (about 16 min 19 sec), including observation/periodic saves |
| Total Docker wall | 1118.1659514 seconds (about 18 min 38 sec), including compile/cold boot/exit; preparation-file creation separate |
| Errors | CFSR/HFSR, memory/system, guard/RTC, GPU rejection all 0 |
| Original executed instruction increase | 1,151,115,163 |
| Frames | first serial 3 → last 13, normal idle after initial fade, no forced redraw |
| HCI version query | six requests/six responses consumed |
| Advertising reconfiguration | one request/response each for stop, params, enable; procedure step 3, advertising-stopped=false, no pending |
| UART0 | actual 334 DMA/7336 bytes, prefix4096/drop3240, FNV13818166612491192142 |
| Final app state | current task IDLE, original ui_task waiting to receive on empty UI queue (capacity96/item12/message0) |

Natural path also retained from original main reset to first screen. Total virtual time: first screen 8.621998 seconds → end 68.660762 seconds. This does not mean execution from actual Boot ROM reset. Before/after SHA of stock main, declared model/board, and original runtime/host guard were audited. Six initial SRAM snapshots and pinned first frame matched.

## Independent saved audit

Private `sustained-final-partial-audit-01/report.json` reaudited capture with frozen runner and confirmed original UI queue literal/TCB and receive wait-list in final full SRAM. It reconnected each DMA source byte recorded by original runtime to independently recalculate 7336 bytes/FNV. Last 576×288-byte frame SHA: `334b2e9559e8cccc795ae753f0735cf2c189f9f41aba9d4299a6e2366e39889a`. Visually inspected gain16 preview and original bytes/manifest are in `sustained-first-60s-preview-01`. This is not optical/physical display review.

Partial audit result **verified_runs1/verified_pairs0, passed=false, full_goal_verified=false** does not contradict first native passed=true. Same-configuration/final-frame matching for two runs per original, all three originals, and new six-second repeats were not yet present. Startup PC and IRQ history are bounded samples, not exhaustive event capture.

## Costs and limits

This is cost of one new integrated-profile run, not performance-improvement comparison, device FPS, arbitrary-load throughput, or sustained-stability evidence. Model uses Docker CPU 1/memory 512 MiB. Maximum observed memory among 65 samples over Docker lifetime was 491.0 MiB. Highest CPU sample 109.93% is sampling-window statistic, not evidence of exact process peak/hotspot or quota violation. Concurrent host load uncontrolled; ranges/medians of further repetitions belong in final cost report.

Host observation limit for first render is explicitly 300 seconds (extended from stock24 original 30 seconds). Earlier execution advanced only virtual 148 ms at host 30 seconds, while normal return required about 234 ms. Guest virtual one-second limit, watchdog, MIPS, and branches were unchanged. Corresponding old2-family first-detail-frame host 120 seconds was also pinned to 300 seconds in the same selected profile. Audit rejects changes outside one known literal.

Sensor/GPU/power/RTC and HCI identity/advertising procedures are explicit functional models. This does not claim support for other HCI parameters/features, RF timing, precise fusion, or all GPU commands. [Required-material gaps](sustained-required-material-gaps.md) are separate determined material. Physical access/flash/Astra/external publication 0.

## Subsequent runs

Worker using same frozen 796 sources started stock24 second 60-second run, then sequentially two each for stock23/Faceclaw 60 seconds and two new six-second runs per original. It stops at first failure without automatic retry. Actual state is checked in `sustained-render-guard-bw505-01/state.json` and current child's process/container. Overall Goal was active 6/10; the first 60-second success was not added as an independent denominator condition.

## Rejection counterexamples for new integrated profile

bw507 used APFS COW copies of first successful 60-second capture to mutate advertising response phase/status, physical-identity claims, unreviewed host 600 seconds, runtime reassignment, and lowered requested time, each rejected by frozen audit. A one-bit mutation of full UART stream hash was also rejected by independent comparison with original DMA list. Seven counterexamples total; all original capture file SHAs unchanged before/after. Zero new ARM runs. Private `sustained-integrated-negatives-01/report.json` preserves rejection layer, failed-check name, and input SHA for each. Distinct from ten earlier six-second counterexamples; not physical recovery certification or actual-original fault injection.

## Stock 2.4 two cold 60-second runs complete

bw508 second cold run passed 60.011987 seconds, fault 0. Model/board/runtime/activation/main and initial input/budget configuration SHAs matched first 60.038764-second run; final frame SHA also matched 334b2e95…. Original UI queue receive-wait/TCB and original UART 7336 bytes/FNV were independently confirmed for each.

New partial audit `sustained-final-partial-audit-02/report.json` is verified_runs2/verified_pairs1 and stock24-60000.passed=true. Overall report passed/full_goal_verified remained false. First/second post-screen wall 978.6361402/1193.5893057 seconds are recorded as two execution-cost samples with uncontrolled host load, not compared as performance regression or physical throughput.

60-stock24 condition was marked complete, active Goal 7/10. New integrated six-second repeat verification across three originals, two 60-second runs each for other two originals, and final cost audit remained. Worker started stock23 first 60-second run. Earlier 6/10 wording is first-success history.

## Stock 2.3 first 60 seconds independently verified

bw510. First cold main run of original stock23 passed 60.017361 seconds post-screen, actual 827.7215826 seconds. Total Docker lifetime 914.567369333 seconds, original instructions +1,106,902,674, frames +10, execution fault/guard 0. Final ui_task waited to receive on original empty UI queue (capacity96/item12), current task IDLE. Final frame SHA matched stock24 at 334b2e95…. This is not expanded to full behavioral identity of versions or physical accuracy.

Original 333 DMA/7306 bytes were independently reconnected to confirm FNV7990547523216551656, prefix4096/drop3210. Across 55 resource samples over lifetime, maximum observed memory 508.3 MiB and CPU 104.83%; not evidence of peak, absence of leak, or hotspot. Private `sustained-final-partial-audit-03/report.json`: 3 runs/1 pair, full_goal_verified=false. Stock23 second run proceeded separately; acceptance stayed 7/10. New ARM work was only worker's approved matrix; independent audit used saved evidence.

## Stock 2.3 two cold 60-second runs complete

bw512. Second stock23 ended at 60.021926 seconds, wall 800.9698417 seconds, execution fault/guard 0. Main/model/board/runtime/activation/initial-input/budget configuration matched first run; final frame matched 334b2e95…. Original ui_task empty receive queue/TCB and actual 333 DMA/7306 bytes/FNV7990547523216551656 were separately verified.

Private `sustained-final-partial-audit-04/report.json`: four runs/two pairs, stock23-60000.passed=true. Stock23 n=2 wall/virtual second 13.344621–13.791369, median 13.567995, execution cost with uncontrolled host load. Overall Goal remained 8/10, partial/full_goal_verified=false. Worker advanced to first Faceclaw 60-second run, actual running owner 97074/container fee5e277799d4424bcdd02e13d1795a7. Full final six/60-second reverification and cost audit remained.

## Faceclaw first 60 seconds independently verified

bw513. First cold run of Faceclaw38 original main ended at 60.010684 seconds post-screen, wall 1019.1387445 seconds, fault/guard 0. Total Docker 1132.1340745 seconds, original instructions +1,150,340,252, frames +10. Final original ui_task waited on empty queue (capacity96/item12), current task IDLE. Final frame SHA 334b2e95… confirmed. Matching stock23 frame does not imply identical behavior in all respects.

Actual 333 DMA/7306 bytes were independently reconnected to confirm FNV7990547523216551656, prefix4096/drop3210. Across 68 resource samples over lifetime, maximum observed memory 510.0 MiB and CPU 116.09%; not evidence of peak, quota violation, absence of leak, or hotspot. Private `sustained-final-partial-audit-05/report.json`: five runs/two pairs, full_goal_verified=false. One run did not complete 60-cfw condition; 8/10 retained, and second Faceclaw actual running owner 13848/container 81449c3f4e174042a624bd7769c6cdbb confirmed.

## Faceclaw two cold 60-second runs and all three originals' 60-second repeats complete

bw515. Second Faceclaw ended at 60.010816 seconds, wall 1068.4437165 seconds, fault/guard 0. Main/model/board/runtime/activation/initial-input/budget configuration matched first run and final frame SHA 334b2e95… matched. Original ui_task empty receive queue/TCB and actual 333 DMA/7306 bytes/FNV7990547523216551656 were independently verified.

Private `sustained-final-partial-audit-06/report.json`: six runs/three pairs, all three original 60-second pairs passed=true. Faceclaw n=2 wall/virtual second 16.982622–17.804186, median 17.393404, execution cost with uncontrolled host load. 60-cfw condition completed, Goal updated to 9/10. Six final integrated six-second repeats and cost/full audit remained, so full_goal_verified=false. Existing worker advanced to stock24 first six-second run, owner 29194/container c3b931b1c8de4cc49e6f0fd80b1cb8e9.
