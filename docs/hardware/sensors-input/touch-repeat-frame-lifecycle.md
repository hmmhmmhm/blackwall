# Repeated touch report lifetime

bw-0453 · E11 partial. Two independent GPIO27 inputs on stock 2.4 original ARM main each led through original IRQ, touch handler, slider dispatch, and caller return. Second app UI consumption, pixel output, ring, and full gesture contract remain incomplete. Overall acceptance remains 10/16=62.5%.

## Implementation scope

Default-off `reusableEventFrames` and host-only `TryLoadEventFrame(byte[])` were added to `tools/renode-iom-register-probe.cs`. A next 16-byte report is copied only after the existing report is fully read, no config reply is pending, and owner.Quiescent is true. Quiescent reflects existing controller transfer, FIFO, submodule, and actual IRQ-line conditions; it does not claim every raw IRQ latch is 0.

Each new report requires a new pointer03 write. Partial consumption, transfer in progress, unconsumed FIFO, completion IRQ, active bus, duplicate load, and incorrect sizes are rejected. A separate host-buffer copy prevents aliasing. Controller reset does not resupply peer input; peer.Reset restores the constructor's original report and counters. This is neither an inferred physical controller FIFO implementation nor automatic repeated input. Wire-read format and existing defaults remain.

## Verification results

- Red: preserved the pre-change constructor's rejection of the new option.
- Synthetic device checks: 86 new checks passed. All JSON values of 59 existing single-report checks matched before/after. Different JSON key order prevents byte identity.
- Natural M55: two distinct GPIO27 low/high pulses supplied on pinned stock 2.4 raw SHA `df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a`, existing 10 MIPS/GAF-profile board. Host did not change original PC, branches, TCB, or readiness.
- First report `020800003412cdab0180ffff5ac317e9`, next `02400aa73412cdab0180ffff5ac317e9`. Original dispatched slider arguments `[1,1,0,0]` and `[1,4,10,167]` respectively. The second is not generalized as the full meaning of a physical gesture.
- Both executed actual original handler `0x4fd75c` and returned to caller `0x5053b4`. Entry/exit SP and TCB matched in Thread context. Two reports, eight read chunks, one reload, two falling edges, and two IRQs were confirmed. Actual GPIO role read count is 2, not exhaustion of budget 4.
- Full SRAM, R0–15, and virtual time were identical before/after reload. Registers and time also remained immediately after second GPIO input. Both pulses released and pending was false. CFSR/HFSR, memory violations, strict guards, and trace overflow were 0.
- Saved artifact audit passed 30 checks. The owned container was removed and the same native run was not repeated.

## Failures and limits

First audit failed by assuming byte-identical JSON. Diff showed only key order differed, so it was corrected to compare all values; the first verifier and failure explanation were preserved. After exporting all results and Renode exiting, native runner has a defect where an outdated summary print queries a nonexistent top-level `stopped` key. Actual `touch.json`, original trace, SRAM, and process journal were independently audited; this output defect is not hidden or claimed as normal runner exit.

Single wake across three originals is separate bw452 evidence. This natural two-report run was confirmed only on stock 2.4. Second UI processing, ring, full gesture/hold/release/continuous input policy, and post-reset input integration are not completed by this result. Font lookup or UI callback entry is not turned into pixel-output success. Normal GAF computation and natural-render prerequisites remain.

## Reproduction material

Outside Git, `simulator/touch-repeat-frame-research-01/` preserves plan inputs, pre-change source, diff, native runner, verifier, and audit results. Red/green and default-before/after directories hold actual model, execution logs, and reports; `touch-repeat-native-01/stock24/` holds actual board, original hash verification targets, trace, and SRAM. Full file list and SHAs are in `simulator/touch-repeat-frame-manifest.json`.

Next compare two-report lifetime on stock 2.3/Faceclaw using the same explicit adapter. Separate UI/ring contracts require original evidence; do not expand to hardware access, forced readiness, or general GAF-ready implementation.
