# Ambiq glyph output target buffer and submission boundary

bw-0247 investigated target ownership after the [original glyph wrapper](font-wrapper-renderer-boundary.md). Original ARM output-target prechecks were executed; GPU command generation/execution and full main screen output were not yet verified. No glasses access or new Renode main run.

## Connections confirmed in original code

| Role | Stock 2.4 | Stock 2.3 / Faceclaw 38 |
| --- | --- | --- |
| Draw-job dispatch candidate | 0x4eb9ba | 0x4e12fa |
| Output-target setup candidate | 0x4d256e | 0x4c4bbe |
| Target format conversion | 0x4d2292 | 0x4c48e2 |
| Draw unit getter | 0x4ebb82 | 0x4e14c2 |
| Getter global slot | 0x200771c0 | 0x20077a38 |
| Target binding call | 0x4d2752 → 0x4d2edc | 0x4c4da2 → 0x4c552c |
| Common post-draw call candidate | 0x4d28ce | 0x4c4f1e |

Dispatch gets a layer candidate from job `+0x48` and a draw-buffer from that object's first word. `+0x4c` is a separate draw-unit candidate. The two fields read by glyph callback must not be directly interpreted as pixel pointer and stride. Structure names are interpretations based on calls/use, not evidence of obtaining exact vendor header/ABI.

After target setup succeeds, dispatch job-type 5 path calls previously identified label entry `0x57614e` / `0x55ca26`. Common post-draw call and draw-buffer postprocessing follow. Label entry passes Ambiq callback to original generic letter. All are static connections here because full dispatch was not executed.

Original target-binding arguments are `0, data pointer, width, height, mapped format, stride, 0`. Width/height are low/high 16 bits of draw-buffer `+4`, stride low 16 bits of `+8`, data pointer at `+0x10`. Before this call, a path compares pointer, size, format, and stride against previous target cached at draw unit `+0x58`. Glyph `context+0x2c` temporary buffer and output target are separate.

The post-draw candidate includes command-list-family calls and paths suspected to wait/check errors. GPU ring submission completion, rasterization, and panel transfer were not confirmed. Exact state contracts for binding and post-draw are next investigations.

## Original ARM function tests

`tools/inspect_ambiq_target.py` checks SHAs of three existing pinned bundles and executes only original RX code. Draw-unit pointer in global slot, output draw-buffer, clip, and work memory are explicit synthetic inputs. Getter and clip calculation/format-check functions execute unchanged; branches/returns are not replaced.

- Target format conversion ran all 0–255 per image, 768 total, identical across three. Supported results: `6→9, 11→11, 12→49, 13→53, 14→9, 15→57, 16→16, 17→17, 18→4, 21→68`; all others `0xffffffff`. Names were not arbitrarily assigned from another enum.
- Six conditions per image, 18 total: color14 normal, color20 normal/special flag, 1×1, out-of-area clip, partial clip.
- Color14 reached just before lock function with mapped format 9. Color20 stopped just before error logger normally; special flag 1 reached just before lock with mapped format 4. This further supports not confusing glyph format 20 with draw-buffer color enum.
- Original returned false for 1×1 and out-of-area clip. Partial clip constrained `[-2,-3,10,11]` to `[0,0,10,11]`. Test size 64×32 and stride 128 are synthetic, not actual framebuffer specification.
- Original input buffer/header and synthetic SRAM were unchanged before/after. Final work-area changes were only on stack. No memory-write hook was used; this does not prove every instantaneous write history.

Even normal cases stopped before entering lock function `0x4d2422` / `0x4c4a72`. Logger was neither executed nor replaced with success return. Without a synchronization contract for draw-unit/command-list state actually created by main, arbitrary active state was not filled to pass submission.

## Evidence and limits

Canonical result is outside Git at `simulator/ambiq-target-contract-03/report.json`, preserving raw SHA, original dispatch/target instructions, 768 returns, 18 boundary results, and tool copy. Separate `simulator/ambiq-target-verification-01/audit.py` has 1,239 checks of pinned bundles, instruction bytes/independent decoding, format table, clip results, three-image correspondence, and test scope. This audit is not new hardware verification.

First tool run failed by assuming the target function's fourth BL was format conversion. An invalid-buffer logger actually comes first, so it was corrected to locate the call using the unique format-function address. Firmware and execution branches were unchanged. `-02` was first success; `-03`, adding static binding arguments and clip/SRAM invariance checks, is final evidence.

Next unit must combine initialization, locking, binding, and post-draw contracts of original draw unit/command list to establish an observable actual command-list boundary. Do not respond success to unsupported GPU commands. Full main reset path, external font-bank, integrated framebuffer/screen, web installation/recovery, and physical safety remain separately incomplete. Product fulfillment remains 13/29=44.8%, scope v2.
