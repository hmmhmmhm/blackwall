# Natural boot and first screen for stock 2.3 and Faceclaw

bw-0481. The user-specified order **screen display → boot → detailed peripheral accuracy** was applied. Stock 2.4 screen/continuous-frame evidence from bw479–480 remains; the other two originals were verified through their first screen using the same functional device model.

## Results confirmed

| Original | Actual execution path | UI callback return | Completed screen | Errors |
| --- | --- | --- | --- | --- |
| Stock 2.4 | Existing bw479 reset→touch→UART peer→UI→GPU packing | Previously confirmed | Existing 576×288 | Existing guard/fault 0 |
| Stock 2.3 | This run reset→touch→UART peer→UI→GPU packing | `0x445694` reached normally | 576×288 | Guard/CPU fault/GPU rejection 0 |
| Faceclaw38 | This run reset→actual patch hook→stock fallback→UART peer→UI→GPU packing | `0x445694` reached normally | 576×288 | Guard/CPU fault/GPU rejection 0 |

New runs were one per original, sequentially. Both obtained completed screen serial 3 after 31 GPU lists and 120 draws. Actual guest L8 source 165,888 bytes had 5,553 nonzero pixels valued 0–13. First-screen raw SHA256 for all three originals matches `5bed2a24ac17aa73a627552376d35af5c27988fd57e60e12faa7c29b55403501`. The host did not draw text or images instead.

A brightness ×16 PNG was directly inspected. Date, status, clock, and dashboard “No news available / Add new sources in the app” are visible. ×16 is for observation; raw files remain unchanged. Physical fidelity of clock/composite colors, subpixels, and more remains unverified.

## Original and device-model boundaries

`tools/run_boot_family_functional.py` pins each original main, board, touch/UART observers, and source-checked UI addresses from bw452. It reuses bw479's completed `strict.cs` byte-for-byte and retains each original's existing version-specific PC-qualified board properties. Retention store/return/flush use existing `reset_restart_profiles.profile` to check actual original instructions and pinned material. No new per-register or duplicate retention implementation was added.

All **six** existing bw452 SRAM snapshots—before/after input, before/after UART reply, app request, and UI dispatch—were byte-exact to each original in this task. There is no evidence the new model changed state before first UI entry. This is not expanded into a guarantee that every observation is nonintrusive.

The initial 10 MIPS interval was retained, applying an explicit 167 MIPS functional profile only in HP mode at actual original UI dispatch. General registers, instruction count, virtual time, and full SRAM matched before/after. Original firmware, PC, TCB, branches, and returns were unchanged. This speed is not a physical performance measurement.

IMU cold bootstrap, constant ambient light, reference GPU packing/texture, and retention functional-model assumptions follow the [first dashboard](../hardware/display-gpu/first-native-dashboard-frame.md) and [functional profile](../hardware/display-gpu/screen-first-functional-profile.md). This does not mean complete implementation of GAF ROM mathematics or physical GPU. Both originals recorded FIFO configuration ready and GAF phase disabled. Services=2 is an existing service counter, not a count of all successful sensor computations.

Actual Faceclaw trace reconfirmed existing `7d3c00→7d3c14→7d3c74→7d3c7e→46a672` fallback path. Host did not create custom state or select Faceclaw's own UI. Thus this is the **stock fallback screen of the Faceclaw image**, not reported as successful custom HUD.

## Verification and preservation

Schema 2 common semantic evaluator distinguishes execution integrity from callback/screen semantic success. The first stock 2.3 run succeeded through guest display, but host auditor compared new runner source against old runner source and failed execution assessment. The failure report was retained and corrected to check the new runner's plan SHA. Only saved material was re-audited; guest was not rerun.

Two saved-material controls with a blank screen and wrong callback-return PC passed execution integrity but were rejected semantically. These are not new ARM runs. Audit tool and nine local Python dependencies were frozen; each original's saved material was independently audited in `/tmp` without PYTHONPATH. Owned containers for both runs were confirmed removed.

Pinned material is outside Git in `simulator/boot-family-functional-manifest.json`, `boot-family-functional-native-01/{stock23,cfw}`, `boot-family-{stock23,cfw}-frozen-audit-01`, `boot-family-semantic-negatives-01`, and `boot-family-screen-viewer-01`. Proprietary originals, SRAM, and images are not added to Git.

## Remaining boot verification

Natural main path through first screen now covers three originals. E05 remains **partial**, overall **12/16=75%**. Task wait/resume and continuous updates after first screen for stock 2.3/Faceclaw have not yet been confirmed, so full boot is not deemed complete. Bw480's 100.695 ms/five-frame and sleep/wake evidence applies only to stock 2.4.

Next verify boot lifetime after the same first screen in those two originals; sensor mathematics, detailed graphics fidelity, and further inputs follow. No physical access, flash/OTA/MRAM write, agent invocation, or external publication occurred.
