# Boot lifetime verification after the first screen

bw480. Previous bw479 verified stock24's first 576×288 dashboard source from natural reset. This task pins the same model, board, and main and observes 100 virtual ms after first screen. Initialization, PC, TCB, branches, and returns are unchanged.

The contract is saved as schema 2 before execution. Because a multi-reset/touch/UI recipe differs from the generic candidate CLI's single observation loop, it reuses `run_native_candidate.py`'s `semantic_spec` and `finish_capture` evaluators. All input and additional NVIC observer SHAs are pinned, separating execution success from semantic pass. Full original main boot and other originals are not completed at once.

- Reach virtual 100 ms, with host 180-second/maximum 32-frame ceilings. Observation timeout is recorded as an end reason, not a firmware hang.
- Reproduce first-screen raw hash, unchanged model/main, and all guard/CPU/GPU faults 0.
- Check at least three original packing-complete sources, order/content changes, and missed count. Host observes actual framebuffer copies without injecting finished images.
- Connect existing sleep-signal observer only after first screen and leave timer PC hooks 0. Separately confirm WFI entry/release pairs and FIFO configuration ready. Disclose bounded event-history overflow without claiming all IRQs were collected.

Success in this interval means limited original task/display lifetime for stock24. E05 requires all three originals, E06 runtime reset re-entry, and E12 actual sample consumption, so they are separate. No physical device, Astra, or publication is used.

## Results

**Under pinned stock24 model, 100.695 virtual ms after first screen ran, confirming five distinct completed frames and actual sleep-entry/release pairs.** Main, device model, and board match bw479. All strict guards, GPU rejections, CFSR/HFSR, and memory-policy violations are 0. This meets E10's declared timing scenario and brings overall to 12/16=75%.

| Observation serial | Maximum pixel value | Source SHA256 prefix |
| --- | ---: | --- |
| 3 | 13 | 5bed2a24ac17 |
| 4 | 27 | 343478445dd6 |
| 5 | 45 | a65f196a48e1 |
| 6 | 66 | 72919d636680 |
| 7 | 89 | c6aa46d7f55e |

All frames are 576×288/165888 bytes with zero missing serials. Fade-in of the same dashboard was confirmed in actual source pixels. Physical FPS is not calculated from these observation times. Original pixels remain unchanged; viewing brightness ×2 was applied only to comparison image/local viewer.

Original IMU wrapper gate is 1→1 and FIFO configuration ready=true. The gate indicates initialization wrapper return, not successful sensor computation/sample processing. Retention preparation/flush counters are each 10→74, not counted as 64 physical power losses/restorations or 64 sleeps. NVIC sleep signal directly showed entry/release pairs; 128-entry event history has overflow=true, so full IRQ history is marked incomplete. This is distinct from frame order/content verification.

First-screen raw SHA256 is byte-identical to bw479. First run 01 also reproduced that screen but failed to create lifetime capture due to an `RxRead` property typo in later instrumentation. Run 02 collected the actual 100 ms interval normally, but first report output failed due to an incorrect dictionary index in host audit result construction. Only audit code was fixed and saved material checked in separate audit output. Neither error was hidden as success or changed device model/firmware.

## Evidence and regression judgments

- `private:simulator/post-screen-lifecycle-native-02`: pinned inputs, pre-execution schema 2 plan, model/run/logs, five frame sources, and lifecycle state.
- `private:simulator/post-screen-lifecycle-audit-03/report.json`: input/component SHA, execution/source integrity, and schema 2 semantic judgment. `execution_passed=true` and `semantic_validation.passed=true` were separately confirmed.
- `private:simulator/post-screen-lifecycle-audit-01/index.html`: local viewer showing five original frames in observation order. `first-last-gain-2.png` compares first/last.
- `private:simulator/post-screen-lifecycle-negatives-01/report.json`: three semantic failures—reordered frames, identical replacement frame, and under-100-ms time material—detected without a new VM. Incorrect semantic conditions do not pass even if native integrity passes.
- `private:simulator/post-screen-lifecycle-audit-bundle-01`: frozen runner and eight dependencies. Saved execution independently audited in `/tmp`, confirming same contract/input hashes/judgment. Historical model was not regenerated with the current candidate builder.
- `private:simulator/post-screen-lifecycle-manifest.json`: final hashes, scope, limitations, and record of both owned containers absent.

E05 requires stock 2.4/2.3/Faceclaw all. This result is stock24's short post-initialization lifetime, not complete E05, long-term stability, runtime reset, new sensor sample consumption, or physical GPU accuracy. Next connect this pinned functional model to other originals' initialization/app-event paths.
