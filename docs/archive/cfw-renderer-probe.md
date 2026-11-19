# Standalone display test of actual CFW drawing code

Status: first 576×288 screen generated and visually inspected in ARM emulation. Full G2 boot, stock display driver, BLE, and lens transfer were not executed.

Size caution: do not equate the 576×288 standalone renderer test with the raw panel 640×480/stride 320 defined by pinned g2flash. Integrated display requires verification of actual original G2 buffer, stride, and transfer coordinates. See [G1 decomp comparison](../research/even-realities-decomp-review.md).

## Code and execution

`tools/render_cfw_probe.py` uses `patches/draw.c`, `draw.h`, and `memory.h` from g2flash commit `845f665e0dfdcfd06b7d3a294388de6f17a5bd59`. It checks the checkout commit and git blob identity of all three files. It neither changes the original nor copies it into the project.

The test wrapper draws text and borders with existing `draw_string` and `set_pixel4`. It builds for the LLVM 21 ARM Cortex-M4 target and executes actual ARM instructions in Unicorn to obtain an 82944-byte packed 4bpp framebuffer. It uses the upstream 6×12 Terminus glyph table; font provenance and license follow upstream material. It does not claim to implement another project's UI or stock font.

The framebuffer was converted to an 8-bit grayscale PNG and visually inspected. This display-only conversion multiplies each nibble by 17 and is not a replacement implementation of the CFW renderer. The text identifies the standalone renderer test.

## Evidence checked

- The ARM function returned and SP was preserved. There were no function, OS, or peripheral stubs.
- The 32-byte sentinels before and after the framebuffer were preserved. This does not mathematically prove absence of all invalid memory accesses.
- Two independent ARM build/runs produced the same framebuffer SHA256.
- The same source and scene were separately built and run as an Apple clang native library; all 82944 framebuffer bytes matched the ARM result. Native buffer sentinels were also preserved.
- The actual PNG was opened to inspect borders, title, explanatory text, and 4bpp brightness differences. FPS, latency, and power were not measured.

Results, source/build/frame hashes, and logs are retained privately in `renderer-probe-02/`. The first ARM-only test is `renderer-probe-01/`. PNG=`frame.png`, raw=`frame.4bpp`, report=`report.json`.

## Usage

```sh
/tmp/blackwall-research-GJjXQFhx/offline-venv/bin/python tools/render_cfw_probe.py \
  /tmp/blackwall-research-GJjXQFhx/g2flash \
  "$HOME/Library/Application Support/Blackwall/recovery/renderer-probe-new"
```

The output path must be new. This assumes the current local environment with LLVM/LLD 21 and macOS clang; no portable distribution environment exists yet. It reads no information, keys, or proprietary firmware.

## Remaining scope

This is a renderer test built separately from pinned upstream source, not a boot of the entire blob inserted into the distributed Faceclaw main. Manufacturing information dependencies during full startup, display lists, textures, actual framebuffer ownership, sensor/input/animation and web transport integration, GPU, and physical lens output remain. This display test does not replace existing web installation/recovery compatibility or the overall simulator goal.

## Scene files and frame sequences

`--scene tests/fixtures/renderer-sequence.json` was added. `tools/renderer_scene.py` converts bounded JSON into CFW primitive calls. It currently supports printable ASCII text and filled rectangles within the screen. The test wrapper constructs rectangle loops and frame order; actual upstream code executes pixel placement and text glyphs. This does not implement the firmware display-list protocol.

Scenes allow at most 60 frames, 64 operations per frame, and 80 characters per text; exact fields, integer coordinates, brightness, and geometry are checked. Code and arbitrary function names are not accepted. C string escaping is applied and compiler trigraph processing disabled. Three rejection tests for out-of-range values, control characters, and invalid types and fields passed.

```sh
/tmp/blackwall-research-GJjXQFhx/offline-venv/bin/python tools/render_cfw_probe.py \
  /tmp/blackwall-research-GJjXQFhx/g2flash \
  "$HOME/Library/Application Support/Blackwall/recovery/renderer-sequence-new" \
  --scene tests/fixtures/renderer-sequence.json
```

Code is built once and frame index passed as an argument. Each frame starts with an empty framebuffer; full ARM/native results and guards are compared. `frame.png`, `frame-001.png`, and so on, packed raw data, and per-frame SHAs are retained. A blank frame is valid. Frame times and intervals are host-defined test order, not measurements of actual firmware animation timing/FPS, BLE updates, or power.

Private `renderer-sequence-01/` generated four frames with different text/rectangle positions and 4bpp brightness. All four frame SHAs differed and each ARM framebuffer matched native. The additional `contact-sheet.png` was opened to check positions and brightness of all four scenes. The existing single screen was also rerun in `renderer-probe-03/`, confirming its frame SHA matched previous `renderer-probe-02/`. Integration with the full main simulator remains.

## Entering display initialization in natural main

bw305 confirmed the `drv_mspi_uled_common.c` initialization path and MSPI0 clock boundary from the existing natural M55's original stack, BL, and diagnostic strings. Evidence is recorded in the [clock and initial configuration contract](../hardware/cpu-memory/mspi0-clock-config-contract.md). D3 changes from not started to partial, but natural main framebuffer, transfer, and viewer integration remain incomplete. The standalone renderer screen above is not presented as integrated display output.
