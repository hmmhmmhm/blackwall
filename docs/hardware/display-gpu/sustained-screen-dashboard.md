# Sustained post-screen execution goal dashboard

**Complete: 10/10 (100%) — verification of six and 60 seconds after screen for three originals and determination of required-material gaps.** This is not a completion rate for full ROM boot, precise GPU/sensor fusion, or one-hour stability. A follow-up full-precision Goal was not activated.

| Original | Actual virtual seconds after screen, 6-second runs (two each) | Actual virtual seconds after screen, 60-second runs (two each) |
| --- | --- | --- |
| Stock 2.4 | 6.017903 / 6.011489 | 60.038764 / 60.011987 |
| Stock 2.3 | 6.005872 / 6.003891 | 60.017361 / 60.021926 |
| Faceclaw 38 | 6.001175 / 6.002039 | 60.010684 / 60.010816 |

All three originals had two runs per duration, 12 runs/six pairs independently audited. Each pair matched configuration and final frame; original UI queue/TCB receive wait, actual UART DMA stream, fault/guard 0, and virtual-time/instruction progress were verified. Main/model/board/runtime/activation SHAs matched across each original's four six/60-second runs. Explicit duration/host budget differences were preserved.

Canonical: private `sustained-final-audit-01/report.json`, passed/full_goal_verified=true, 12 runs/six pairs/three integrations passed. Originals, pinned source, initial SRAM, and 15 required material assets were rechecked. Worker 43842/child execution terminated and owned Docker containers for 12 completed captures confirmed absent.

## Execution cost and limits

Post-screen wall time for 60 seconds was approximately 13.3–19.9 minutes by original/run; six seconds took approximately 86.3–171.2 seconds. These costs include uncontrolled host load, observation, and sample storage, not performance ranking or physical FPS. Resource samples from all runs were checked. [Full cost of 12 runs](sustained-execution-costs.md).

One stock24 six-second attempt under the same final profile stopped at first detail-frame host 90-second limit (virtual 45.294 ms). A separate stats 15-second timeout was also preserved. A manager separating resource collection errors from native lifetime ran new tests without changing input/model/runtime/budget. Seven successes were reused and only remaining five run. Failure was not added to success statistics.

## Required-material gaps determined

- Actual Apollo510B Boot ROM/reset and Info1/security initial state: unavailable. Current main reset execution and possession of original bootloader are not full ROM boot.
- GPU: exact IP rules and independent pixel output/oracle lacking. Current reference functional model is not counted as physical accuracy.
- GAF: EDMP ROM/ISA and calculation specification or independent numerical input/output reference lacking. FIFO, original host decoder, and axis conversion are not full fusion reproduction.

[Gaps and acquisition paths](sustained-required-material-gaps.md). Completion of these gap conditions means missing materials were identified, not precise implementation completed.

## Verification and cleanup

[Final completion report](sustained-goal-completion.md) · [Final six seconds](sustained-final-six-second-results.md) · [60-second history](sustained-first-sixty-second-results.md) · [Plan](sustained-screen-plan.md).

Ten behavior rejections, seven new integrated counterexamples, and 34 related unique unit checks were confirmed. Signal/startup PC records are bounded samples; exhaustive observation of every event/IRQ/frame is not claimed. Physical access/flash/Astra/external publication: 0.

After work, 507 reproducible Python caches totaling 6,510,546 logical bytes were cleaned; follow-up checks/tools ran with `-B`/bytecode disabled. Disposable containers from Docker execution output were removed, while major analysis, pinned inputs, and final audit evidence remain.
