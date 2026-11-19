# Post-first-screen lifetime across three originals

bw-0482. This follows the user's priority of verifying boot lifetime after obtaining a screen. Stock 2.3/Faceclaw first-screen runs from bw481 were pinned, and the 100 ms observation applied to stock 2.4 in bw480 extended to both originals. Original firmware, board, and common device model were unchanged.

## Actual execution results

| Original | Virtual time after first screen | Completed frames | Content change | CPU sleep entry/release | Guard/CPU fault/GPU rejection |
| --- | ---: | ---: | --- | --- | --- |
| Stock 2.4 | 100.695 ms, existing bw480 | 5 | Fade-in | Confirmed | 0 |
| Stock 2.3 | 100.107 ms, this run | 5 | Fade-in | Confirmed | 0 |
| Faceclaw38 | 100.120 ms, this run | 5 | Fade-in | Confirmed | 0 |

Both new runs began at original reset and traversed existing touch, virtual UART peer responses, and original UI path. First-screen raw SHA reproduced `5bed2a24ac17aa73a627552376d35af5c27988fd57e60e12faa7c29b55403501`. Completed frame serials were 3→7 with zero missed frames. L8 maxima changed 13→27→45→66→89. First/last PNGs at viewing brightness ×2 were also inspected. This is not physical FPS or device latency measurement.

Sensor wrapper gate was 1→1 for both originals and FIFO configuration ready=true. Gate evidences original wrapper return, not success of sensor mathematics or every lower-level error check. Functional assumptions of GAF cold bootstrap, constant light, reference GPU, and retention remain.

Retention preparation/flush counter was 11→78 in stock 2.3 and 12→96 in Faceclaw. These are not physical power-cycle or actual sleep counts. Both 128-entry NVIC observation histories overflowed, so total IRQ/sleep counts are not claimed. Only sleep-entry/release pairs within saved history were confirmed.

## Pinned inputs and observation boundaries

`--case stock23|cfw` was added to existing `tools/run_post_screen_lifecycle.py`. No separate per-register runner or device model was made. Default stock24 CLI and saved audit remain.

- Each original's bw481 manifest, main, board, execution script, and observer were SHA-pinned.
- Existing sleep-signal observer is connected only after first screen; there are no additional PC hooks.
- Six SRAM snapshots for both new originals—before/after input, before/after UART reply, app request, and UI dispatch—are byte-exact to bw481.
- Gate address `0x20077d00` for both families is derived by confirming actual main `0x4baae6` LDR.W and original store at `0x4bab40–44`. Host does not write the gate.
- Maximum after-first-screen limits were 100 ms virtual, 180 seconds host, and 32 frames; both runs ended at virtual limit.
- PC/TCB/branches/returns were not forced. Both owned containers were confirmed removed.

Faceclaw also saved full SRAM before observation. This extra export is a guest RAM read, not firmware modification. The absence of that before-window export in stock 2.3 and existing 2.4 is explicitly retained.

## Scope of task behavior confirmed

Existing UI observation traces for all three originals each show four app 1 event type 4 callbacks after first screen. All ran in actual `ui_task` TCB and Thread mode with no trace overflow. Final SRAM also confirmed that task's event-list membership, bidirectional links, owner, and count.

However, this does not establish direct chronological evidence of the **waiting state → resumption instant**. At first observation Faceclaw UI task was not yet on the event list, and the other two originals lack full pre-observation SRAM. Final waiting state is not joined backward to earlier repeated callbacks.

E05 therefore remains partial. Next verification must actually capture waiting state during the same 100 ms interval, then pair that TCB with later original callback entry. For example, briefly pause the whole machine at 10 ms after first screen to read task/list, then resume original event processing. This observation change needs separate input/records and does not write PC/TCB. Do not arbitrarily add a longer time goal or reduce acceptance criteria.

The old full TCB scanner failed pointer-range checks on existing stock 2.4 post-screen SRAM. That diagnosis was retained and not interpreted as full task-graph verification success or firmware corruption. This limited UI event-list analysis does not substitute for success of the full scanner.

## Audit and progress

Both schema 2 common semantic judgment and execution-integrity checks passed. Saved audit tool and eight local dependencies were frozen, and each of three originals re-audited in `/tmp` with empty PYTHONPATH. Stock 2.4 used existing material without new ARM execution, confirming CLI-extension compatibility.

Material with another original's initial SRAM was rejected by execution-integrity checks; material with a post-first-screen GPU fault was rejected semantically. These two controls are saved-material mutations, not new guest runs.

All three originals have evidence of post-first-screen CPU progress, fade-in, and sleep/wake, but E05 still needs direct pairing of task wait→resume. **Overall acceptance remains 12/16=75%**. E06/E11/E12 remain; no physical access, flash/OTA/MRAM write, agent invocation, or external publication occurred.

Pinned material is outside Git in `simulator/boot-family-lifecycle-manifest.json`, `boot-family-lifecycle-native-01/{stock23,cfw}`, `boot-family-lifecycle-frozen-audit-01`, `boot-family-lifecycle-task-analysis-01`, and `boot-family-lifecycle-viewer-01`. Proprietary ARM, SRAM, and raw images are not committed to Git.
