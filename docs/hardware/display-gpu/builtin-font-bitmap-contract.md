# Original built-in font bitmap conversion contract

bw-0240. Actual pixels were obtained from the original ARM bitmap callback. **This is an isolated function conversion test, not yet natural UI rendering, framebuffer, or panel output from the original main.** The external font bank was not replaced, and initialization was not skipped.

## Capturing original initialization state

The existing low SRAM copy contained font objects but not the high SRAM containing the stride calculation dispatch. Instead of supplying that value arbitrarily, we ran from the pinned main reset, stopped at the existing XIP guard, and read it afterward.

Using the schema2 common runner's `font-draw-buffer-candidate.json`, we collected 4 KiB from 0x20070000 for each of the three inputs. The stock 2.4 handler was at 0x20070810, but the older/CFW handlers were outside that range at 0x20071450. After confirming the address by static disassembly, we collected only the relevant 32 bytes for those two inputs with `font-draw-buffer-extra-candidate.json`. The five native runs are new observations to capture this missing state, not purposeless repetitions of the same evidence.

All five runs exactly matched their respective baselines for original CPU, instruction count, device state, and events. Code, models, and observations during execution were unchanged, and reads were performed only after stopping. The new common semantic contract also passed. Inputs, logs, and judgments are preserved in private `font-draw-buffer-main-01` and `font-draw-buffer-main-02`.

## Function arguments and ownership

`tools/inspect_builtin_font_glyphs.py --bitmap-contract` is a mode separate from the existing glyph investigation. It maps the pinned main as RX and restores only the original low SRAM and the additionally collected handler. A hook rejects accesses to other uninitialized SRAM. It does not change original opcodes, branches, function returns, or MMIO.

The isolated function call uses synthetic arguments, stack, output structure, and caller buffer. It explicitly requires the caller to supply the descriptor's resolved_font field. An initial exploration failed with a null access when this field was omitted. This preparation is not evidence that the actual original UI wrapper performed it.

- Pass the glyph ID returned by the actual descriptor callback to the bitmap callback.
- The bitmap callback uses the font at descriptor+0, format data at font+24, and glyph ID at descriptor+24.
- It writes A8 pixels to memory pointed to by draw-buffer argument+16. The stride callback registered by original initialization also runs as actual ARM code.
- Two different caller buffers produced the same pixels; for nonempty glyphs the return value equaled the draw-buffer argument. Empty glyphs returned 0.
- There were no writes outside the target pixels and stack, canary damage before or after the buffer, descriptor changes, or SP/callee-saved register corruption.

Borrowing the caller buffer is confirmed for this path. Allocation and release of generic draw buffers and lifetime management by the UI caller remain unverified. The +8 slot of every font object was 0, but this alone does not establish that all font release operations are unnecessary.

## Pixel format and comparison

The five selected built-in fonts use the original descriptor's 4bpp, format3 path. The original expanded nibbles to 0, 17, …, 255 and output A8. The observed source row stride is `floor(width/2)+1`. The first independent interpretation assumed the usual `ceil(width/2)` and failed on the width-8 g. It matched after accounting for the original loop's additional increment at the end of each row. No claim is made about the intent of this behavior or equivalence in other LVGL versions.

For each input, space/A/W/g/α/Cyrillic А/😀 were queried in five fonts. Supported glyph bitmaps were called in two buffers: 96 calls total, comprising 30 empty glyphs and 66 actual pixel conversions. Original callback output matched the independent packed ROM interpretation byte for byte, and compared glyph IDs, dimensions, and pixel hashes were the same across stock 2.4, 2.3, and CFW. Not every declared glyph or all Unicode bitmaps were exhaustively verified.

We created and visually inspected private `builtin-font-bitmap-contract-04/glyph-sheet.png` from data matching the original returned pixels byte for byte. Columns are space/A/W/g/α/Cyrillic А/😀; rows are the five fonts in the order of the existing document. Unsupported cells are blank. This is a font-test preview, not a G2 screen capture.

## Evidence and remaining integration

The later bw246 [original wrapper and renderer boundary](font-wrapper-renderer-boundary.md) confirmed that the original wrapper creates resolved_font, and traced buffer reuse and release through to immediately before the generic letter → Ambiq callback. It does not extend the isolated bitmap evidence here to success of the entire main/display.

Private `builtin-font-bitmap-contract-04/report.json`: 96 original ARM bitmap calls and 863 analysis checks. `builtin-font-bitmap-verification-01/report.json`: rechecking of 33 source pins, semantic verification of five native runs, preservation of analysis code and dependencies, and image hash and visual review records. Initial failures 01–03 are not completion evidence.

Reproduction:

```sh
blackwall_sim="$HOME/Library/Application Support/Blackwall/simulator"
"$blackwall_sim/venv-02/bin/python" tools/inspect_builtin_font_glyphs.py \
  "$blackwall_sim" "$blackwall_sim/my-new-bitmap-contract" --bitmap-contract
```

The next display task is to connect the original font wrapper's resolved_font setup, buffer lifetime, and actual render caller to the framebuffer/submission. A normal external font bank also remains unavailable. After completing this limited unit, the plan moves to W5 virtual web installation and recovery integration. Boot/display and actual installation/recovery remain incomplete. The overall 13/29=44.8% and per-device approval boundaries remain in force.
