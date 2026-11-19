# Repeated six-second post-screen results across three originals

Intermediate result during bw494. **Three six-second conditions completed; 60-second conditions and overall Goal remained incomplete.** Fixed scenario starts from original main reset, produces initial screen on one temple's declared functional model, then sustains it without further input. Faceclaw38 uses existing stock UI fallback and does not test all CFW user features.

| Original | Actual virtual duration, two runs | Post-screen wall time, two runs | Final frame |
| --- | --- | --- | --- |
| Stock 2.4 | 6.000787 / 6.003646 seconds | 98.54 / 94.00 seconds | serial 13, repeat bytes match |
| Stock 2.3 | 6.002694 / 6.003718 seconds | 83.75 / 85.53 seconds | serial 13, repeat bytes match |
| Faceclaw38 | 6.001199 / 6.001166 seconds | 88.01 / 86.75 seconds | serial 13, repeat bytes match |

Each comprises two independent cold-main runs. For each original, both runs had identical hashes for main/model/board/runtime/activation/probe, initial SRAM/ITCM input, and time budget. Screen remained after initial fade-in; no forced redraw without request. Each run had zero faults, memory/system-control violations, unsupported guards, and GPU rejections, with virtual time, instructions, sleep/resume, and cumulative IRQ progressing.

## Additional verification of saved material

`tools/audit_sustained_completion.py` reaudits captures using frozen version of original matrix tool and reads original main UI queue literal load to locate actual queue in final full SRAM. It checks messages 0/capacity 96/item 12 and bidirectional links/owner of original ui_task receive-wait list. Final screen also matches in each repeat. This differs from judging solely by instruction-count increase; it does not establish every task or all UI input responses.

Previous general TCB scanner rejected a memory candidate with empty name/container 0. It was not altered to declare entire kernel normal, and original SRAM was unchanged. This check is limited to active receiver links pointed to by actual original UI queue root. It does not establish all heap/FreeRTOS lists.

Copies of actual parsed captures and SRAM were mutated with early termination, host timeout, guard access, stalled instructions, signal-total mismatch, first-frame mismatch, and UI pending/owner/cycle errors and rejected. An additional copy reducing output target from six seconds to 100 ms was rejected for requested-budget mismatch even if individual state checks passed. Ten negatives total; original captures retained. No new ARM runs.

## Cost measurement scope

Times above are post-screen interval including checkpoint, observation, and storage. Docker time in separate `host-measurement.json` also includes dynamic compilation/cold boot. They are not physical FPS, device clock performance, or throughput for all long-running workloads. Two runs per original are a small sample; 60-second cost remained under measurement.

Docker limits: CPU 1, memory 512 MiB. CPU samples during execution were near one-core capacity; per-run maximum observed memory approximately 475–512 MiB (first reused run one sample/490.9 MiB). These are maxima of periodic samples, not process peak, heap leak, or hotspot measurements. Final cost distinguishes computation waiting and compilation/initial boot.

New signal observer preserves all cumulative counters but limits historical samples to 128. Existing startup PC trace is also truncated over long intervals. Neither is exhaustive event/frame capture or evidence of observation noninterference. Original CPU branches, returns, and TCB were not forced.

MSPI0/JBD5a01 is explicit virtual input of an existing verified model. Earlier first-screen model's strict stop at 1.558 seconds was preserved separately from this profile. This does not certify physical state, GPU/sensor precision, ROM boot, or physical installation/recovery.

Canonical material: private `simulator/sustained-matrix-partial-audit-03/report.json` (six runs/three pairs/resource samples), `sustained-semantic-negatives-01/report.json` and frozen assessor/queue auditor, original captures and source in `sustained-matrix-bw492-01`. Partial report `passed=false`/`full_goal_verified=false` means all 12 runs were not yet complete. Do not carry forward prior v3 100% as this [current Goal dashboard](sustained-screen-dashboard.md).
