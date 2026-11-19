# Original font wrapper and Ambiq renderer entry boundary

bw-0246. The resolved_font previously supplied by caller in standalone bitmap-callback testing is now **created directly by original generic wrapper**. Original letter-preparation function also executed up to immediately before actual Ambiq callback entry. Backend body, framebuffer, and full-main screen output have not yet executed.

## Functions and connections confirmed

| Role | Stock 2.4 | Stock 2.3 / Faceclaw |
| --- | --- | --- |
| Generic descriptor wrapper | 0x508b58 | 0x4ea368 |
| Generic bitmap wrapper | 0x508aaa | 0x4ea2ba |
| Generic release wrapper | 0x508afc | 0x4ea30c |
| Generic letter preparation | 0x49fe26 | 0x493f7e |
| Draw-buffer reshape | 0x4a083e | 0x494996 |
| Ambiq letter callback | 0x57636c | 0x55cc44 |

Each prologue signature occurs once in each of three pinned mains; actual instructions/calls were compared. Raw halfword BL search can include coincidental data patterns, so these are recorded as **static caller candidates**, not proof of full executability.

2.4 `0x576158` forms callback `0x57636d` using ADR and passes it at `0x57615c` to character traversal `0x49f766`. `0x49fd0c` in traversal calls generic letter. Corresponding 2.3/CFW points are `0x55ca30/0x55ca34 → 0x4938be → 0x493e64`. Literal pool near callback and `lv_draw_ambiq_letter.c` path were compared too.

Generic letter contains descriptor, conditional bitmap, indirect backend, and release sequence. Bitmap call may be skipped depending on format. Three separate bitmap-wrapper call candidates exist within Ambiq callback. Backend target buffer and GPU submission remain unverified.

## Original ARM execution evidence

New `--wrapper-contract` mode reuses existing frozen main/SRAM/stride handler. No new native main run or device access. Function arguments, work buffers, and return boundaries are synthetic; opcodes, branches, and function returns are not replaced.

Descriptor starts filled with 0xA5. Original wrapper initializes 32 bytes and sets resolved_font according to actual callback result. Missing characters return null without bitmap call. Fallbacks of five embedded fonts are 0 in this snapshot. **This is not a completed font-chain test**; descriptor-null external-font risk remains.

For existing representative characters in five fonts across three images, bitmap wrapper and release executed 96 times: 30 empty glyphs, 66 with actual pixels. Pixels, glyph IDs, and dimensions from two caller buffers matched previous raw callback and independent ROM interpretation. Pixels and descriptor remained after release. This is embedded font with entry 0/release callback 0; allocation/free of generic cache or dynamic fonts is not established.

For 33 nonempty samples, original reshape was run both with sufficient and insufficient capacity. With sufficient capacity it reused existing draw-buffer and data pointer; with capacity 0 it returned null without changing header. Initial test reused glyph format as color format. Original caller showed the enums differ; final condition corrected to **draw-buffer color 14 / glyph format 20**. Stride equaled each width. Initial condition is not final evidence.

Additionally, A was executed once per image from actual generic-letter entry. Synthetic draw context, clip, coordinates, and already-owned reusable buffer were passed; execution stopped at actual Ambiq callback address. Callback was not returned as mock success.

- All three called original descriptor/reshape and reached callback entry.
- Backend arguments were original draw context and glyph context, remaining two arguments 0.
- resolved_font was corresponding first embedded font, area `[10,16,20,31]`, glyph box 11×16.
- Glyph descriptor is at current SP+12, area at SP+44 on **caller stack**. If backend retains them, lifetime handling is needed; actual asynchronous backend use remains unconfirmed.
- Cached draw-buffer/data pointer stayed unchanged and data remained 0xA5. This prefix is **preparation**, not successful drawing.

576×288 clip is a synthetic input for this function test, not evidence of actual panel/framebuffer specification.

## Observation-hook issue and verification scope

Same original memset(32) was compared on Unicorn 2.1.4. Without hooks or with code hook only, it returned normally and initialized exactly 32 bytes; in two cases adding memory-write hook, loop progressed incorrectly after conditional STM. Arguments matched and firmware bytes were unchanged. Results: private `font-wrapper-memset-hooks-01/report.json`. This observation is not interpreted as actual-device memset bug.

Wrapper mode does not use harmful write observer. ROM is RX, initial SRAM read-only, and reads limited to initialized ranges. Full WORK before/after is compared to reject final changes outside descriptor, draw header, pixels, and stack; canaries/ABI also checked. This does not prove every transient write history. Earlier leaf-callback mode inputs and historical results were preserved.

Final private `font-wrapper-contract-07/report.json` records 1466 checks, 96 bitmap calls, 66 reshape calls, and three letter prefixes. 108 checks in `font-wrapper-verification-01` rechecked pinned native assets, previous pixel/preview identity, format distinction, actual area, stack lifetime, Ambiq static connections, and source pins. Two static-discovery tests passed. Final glyph sheet was opened and visually checked; byte-identical to earlier callback preview. It is not a G2 screen capture.

Reproduction:

```sh
blackwall_sim="$HOME/Library/Application Support/Blackwall/simulator"
"$blackwall_sim/venv-02/bin/python" tools/inspect_builtin_font_glyphs.py \
  "$blackwall_sim" "$blackwall_sim/my-new-wrapper-contract" --wrapper-contract
```

## References and next boundary

Original contains an `lvgl_v9.3` path string, but that does not guarantee exact upstream tag/ABI identity. Comparison source [LVGL font source](https://github.com/lvgl/lvgl/blob/c033a98afddd65aaafeebea625382a94020fe4a7/src/font/lv_font.c) is v9.3.0 commit `c033a98afddd65aaafeebea625382a94020fe4a7`, MIT. Source SHA is 15066979…81f3, license SHA 27a80bd3…cbe8; full values/files in private `font-wrapper-research-01/lvgl/sources.json`. Vendor lock/flag behavior was judged from actual ARM, not by copying upstream structures unchanged.

Next identify owner of Ambiq callback target buffer, format, and stride, and actual renderer/submission arguments. Missing external font-bank, full main boot, framebuffer/panel output, web installation, and physical recovery are not replaced by this result. No new GPU driver implemented. Product 13/29=44.8%, scope v2 remain.
