# Natural UI initialization and font-lookup progress

bw-0447. Saved stock 2.4 natural M55 execution from bw446 was analyzed, and bounded call observation added under the same 1000 ms virtual limit. Physical device, firmware opcodes, PC, TCB, and readiness were unchanged. Overall acceptance 10/16=62.5%; E09/E11 partial.

## Meaning of saved execution

Previous final PC `0x457bb4` was immediately before memset-wrapper return. At current `ui_task` SP `0x2001fef8`, frame sizes were calculated from function-prologue saved-register counts and local stack sizes, and original BL targets immediately before saved LRs compared. This was not merely finding code-like values on stack.

| Function | Frame size | Actual original caller |
| --- | ---: | --- |
| memset wrapper `0x457ba2` | 8 | `0x508a2e` |
| Zero-initialization helper `0x508a28` | 8 | `0x508bb8` |
| Generic font descriptor `0x508b58` | 48 | `0x508cd2` |
| Font width lookup `0x508c8c` | 48 | `0x49edde` |
| String traversal path `0x49ed40` | 64 | `0x49ef68` |

Font is `0x20002954`, output descriptor `0x2001ff38`. Original r2/r3 saved in descriptor frame are 101 (`e`)/32 (space). Original caller requested 32-byte initialization and capture showed that area all 0. This evidences original UI querying string font information, not bitmap generation or framebuffer output. Full unwind beyond five frames was not verified.

Initial analysis assumption that next character was also 101 was disproved by actual saved r3=32. Failed analysis was preserved diagnostically and rechecked with correct arguments.

## Observation contract

New observer records descriptor entry/epilogue counts and first/last registers, counts for at most 256 characters, and first/last 32-byte descriptors only. It separately counts app initialization `0x54c648`, its caller return `0x4b7ad4`, Ambiq letter `0x57636c`, and UI caller return `0x4456ec`. Read observation can affect scheduling; hook-off/on exactness and physical timing are not claimed.

First native attempt selected runner's default `app` breakpoint and ended before UI observation stage. It is excluded from UI success evidence. Next attempt explicitly supplies `normal pulse valid gate` arguments, not a change to runtime or device model.

## Results and limits

Final native03 newly executed original reset → touch → UART ACK → UI callback → app initialization. `strict.cs` and `board.repl` are byte-identical to previous native06. Only observation source was added; CPU speed, timers, and device-response policies were unchanged.

- Actual `ui_task` entered app initialization `0x54c648` once in Thread mode.
- Generic font descriptor entered 888 times, returned to original epilogue 887 times. Character counts: 33 kinds/888 calls. Last PC is next descriptor entry.
- First lookup was `T` (84), next character `e` (101), font `0x77746c`. Actual return R0=1 and 32-byte descriptor containing the same resolved_font pointer were confirmed. Last returned sample also R0=1. Success of every intermediate return was not counted.
- App-initialization caller return, UI-callback caller return, and Ambiq letter entry were all 0. Bitmap/framebuffer output unverified.
- Observation interval about 1025 ms is final progress exceeding nominal 1000 ms limit through host polling and pause. It is not interpreted as real-time performance or actual hardware-time measurement.
- CPU faults, strict accesses, memory-protection violations, and observer overflow were 0. After normal termination all three attempts' owned containers were confirmed removed.

Native02 failed saving JSON because .NET Dictionary `.items()` was unavailable. Only storage code iteration was changed to `.Keys` for native03. Failed execution is not included as success. `attempts.json` privately records this, initial breakpoint-selection failure, and analysis-argument correction.

This evidences UI progress through repeated font-width lookup. It does not prove infinite loop, deadlock, full boot completion, or successful screen output. Next trace whether same strings/objects are reprocessed and layout initialization termination conditions by call, then identify path to actual draw submission. Merely extending runtime is not the next solution.

## Verification material

Private `simulator/ui-initialization-research-01/stack-provenance.json`, `verification-report.json`, pinned runner/observer, and native01–03 are hashed by `simulator/ui-initialization-manifest.json`. Final audit checks original hashes, five frames based on source sizes, actual callers/returns, identical device configuration, character counts, protection boundaries, and process cleanup. Proprietary binaries remain outside Git.
