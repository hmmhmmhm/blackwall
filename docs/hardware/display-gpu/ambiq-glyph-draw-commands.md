# From original glyph bitmap to draw commands

bw-0249 connected original font and glyph helpers to [RAM command-list writing](ambiq-command-list-emission.md). Original descriptor → original raw bitmap lookup → original Ambiq helper → coordinate, matrix, and draw command writing were confirmed. A separate full generic-letter function test failed on a null draw-buffer read. The successful standalone-function path does not replace that failure.

## Successful standalone-function path

`tools/inspect_ambiq_glyph_commands.py` reuses low SRAM font objects and stride-dispatch snapshot captured in earlier native main. Input hashes were compared to pinned hashes in existing `font-wrapper-contract-07`. Original code/snapshots were unchanged.

Synthetic Nema state and a preallocated command list were created and original bind executed. For A, W, and g in the first embedded font, original generic descriptor was queried, `req_raw_bitmap` set, and original bitmap wrapper called with caller-owned draw-buffer. Returned pointers matched original ROM bitmap base + glyph offset; data pointers were not replaced with arbitrary images.

That ROM pointer, actual glyph dimensions and format 20, synthetic area/white color, and helper flags `1,1` matching original callback's packed path were passed to original glyph helper. It wrote these commands to RAM and returned normally:

- Source texture ROM pointer, format, stride, and dimensions.
- Glyph color.
- Transformation matrix reflecting area origin.
- Rectangle start/end coordinates and draw command.

Original helper is stock 2.4 `0x5761c0`, stock 2.3/Faceclaw `0x55ca98`. Synthetic area origin is `(10,16)`. Actual descriptor dimensions: A=11×16, W=13×16, g=8×16. `packed stride=width//2+1`; code also sets source texture width 10 for even-width g. This padding is not interpreted as displayed glyph width 10; draw area uses actual width 8.

Three images × three glyphs = **nine cases**. Bitmap bytes/hash, glyph IDs, and sizes matched across versions. Stock 2.4 wrote 40 words, stock 2.3/Faceclaw 32. Prefix commands differ; both older versions matched under same conditions. Different command counts alone do not establish errors, performance differences, or screen differences. First tool incorrectly assumed 40 words for all versions and failed; after investigating per-version original results, full prefix and common suffix order were pinned and checked separately. Repeated command keys cannot be missed by dictionary-only comparison.

Original unbind end marker was also confirmed. Glyph pixel buffer stayed unchanged. Thus **CPU wrote commands for GPU execution**, not actual framebuffer pixels.

## Failure of full generic-letter test

The same font and synthetic task/layer/unit/clip plus adequate reusable draw-buffer were configured, and execution began at original generic-letter entry. Unlike earlier wrapper test, actual Ambiq callback continued to execute.

All three images stopped with null draw-buffer passed to bitmap callback:

| Input | Error PC | Actual original instruction |
| --- | --- | --- |
| Stock 2.4 | 0x4d9e78 | `ldr.w sb, [r5, #0x10]` |
| Stock 2.3 / Faceclaw | 0x4c6638 | Same |

R5 is 0 at this point. Callback reads draw-buffer `+0x10` before checking `req_raw_bitmap`. This evidences mismatch between original callback null argument and consumer-code requirement on this synthetic path. Address 0 was not mapped, and observer did not change branches, returns, or function arguments. Command-list offset was 0 at failure.

It was not yet established that actual main uses this font/callback combination at that time. Font initialization after snapshot, actual UI font selection, and external font-bank were unverified, so **do not conclude a physical firmware bug or create a patch.** The successful test passing caller-owned buffer does not prove the full caller path succeeds.

## Engine and verification scope

These function tests ran on an auxiliary **Unicorn Cortex-M7** CPU profile with CP10/11 and FPEXC explicitly enabled, distinct from Renode M55 integrated-main testing. No opcode/branch/return substitutions or hooks; original main was RX and snapshot SRAM guest read-only. Final WORK changes stayed in declared object/list/stack ranges; data buffers and SRAM unchanged. This does not guarantee every instantaneous write history.

In earlier separate helper diagnosis, F64 conversion under another synthetic flag combination reached an invalid-instruction boundary in Unicorn M7 (`ambiq-glyph-research-02`, PC0x57632a). It was not forced to execute and original instructions were unchanged. The nine packed-path cases above returned without that instruction. This auxiliary engine is not evidence of full M55/FPU support.

Final evidence is outside Git at `simulator/ambiq-glyph-commands-05/report.json`. Tool/dependency copies and SHAs, existing native snapshot hashes, original pointers/bitmap hashes/command words for nine glyph cases, and three full-caller failures were preserved. `-01` through `-03` are earlier attempts failing command-count assumptions and resulting fixed endpoint; `-05`, strengthening full-order/snapshot-pin checks after `-04`, is canonical.

**202 checks** in `simulator/ambiq-glyph-verification-01/audit.py` separately compared input/tool hashes, existing glyph results, ROM pointers/bytes, actual commands/matrices/coordinates, and null-buffer error instruction. `passed=true` is passage of this limited contract; `full_letter_succeeded=false`. Python compile passed.

Next reproduce this helper test on Renode M55 and identify actual full-main font/callback selection and initialization state. GPU submission/execution, integrated framebuffer/screen, and web installation/device recovery remain incomplete. Product 13/29=44.8%, scope v2 remain. No glasses, case, or persistent-storage access.
