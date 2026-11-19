# Original ARM list-generation contract for display-buffer conversion

At bw346's 102-word boundary, original conversion function and blend compiler were executed. **All three images—stock 2.4, stock 2.3, and Faceclaw—generated lists exactly matching the capture's 102 words.** This evidences command generation, not GPU sampling, nibble order, quantization, or full-screen output.

## Configuration established by original caller

The original function receives source address, destination address, width, and height. Odd width produces no conversion list. Even width uses:

| Stage | Values confirmed in original code and generated list |
| --- | --- |
| Display target | TEX0 L4, width×height, stride width/2 — prepared by caller |
| Conversion target | TEX2 AL44 at same address, width/2×height, stride width/2 |
| First source | TEX1 A4, width×2×height, stride width |
| First matrix | x scale 4, x offset −2, y scale 1 |
| First blend | Original function arguments corresponding to `nema_set_blend(1, 2, 1, -1)` |
| First shader | IMEM `080c0102 / 8a0761c7`, CODEPTR `181f8000` |
| Constant color | `ff000000` |
| Second source | TEX1 L4, width×2×height, stride width |
| Second matrix | x scale 4, x offset 0, y scale 1 |
| Second blend | Arguments corresponding to `nema_set_blend(0x10000101, 2, 1, -1)` |
| Second shader | IMEM `080c0102 / 80076185`, CODEPTR `181f8000` |
| Draw | Each pass submits width/2×height rectangle; caller clip restored at end |

Pinned upstream `nema_blender.h` defines `0x10000000` as `NEMA_BLOP_FORCE_A`. The second mode is FORCE_A and ADD, with output ROP `0x101`. The same header's public `nema_set_blend` argument order is mode, destination texture, foreground texture, background texture. Treating this as ordinary SRC/ADD with TEX0 destination produces a different shader. Actual first shader is reproduced with TEX2 destination, and second must include FORCE_A to match.

Absence of constant shader bytes in ROM alone does not establish custom shaders or separate manual upload. Original blend compiler assembles the commands at runtime. Different output from an earlier simple probe is preserved as diagnostic history using wrong destination/options.

## Verification scope

`original_packing_commands` in `tools/verify_nema_ring_consumer.py` executes existing original bind/texture functions and the full conversion function. Engine is auxiliary Unicorn Cortex-M7, not main-reset/RTOS integration or GPU execution.

- Original main was re-extracted from pinned research bundle and compared by bytes/hash with saved main.
- SRAM uses all 0x380000 bytes of existing native capture. Separate synthetic command list/state and caller clip are declared; original ROM is write-protected.
- Original CPU generates the list without hooks, callee stubs, or MMIO mapping. Call return PC/SP and callee-saved registers are checked.
- Source/destination pixel memory did not change. This function did not calculate display pixels on CPU.
- Actual ring headers/SRAM lists of three native captures were compared to historically preserved packets/hashes, then to the new 102 words. Each image used its actual source address.
- Per image, 2×1, 6×3, and 10×5 at different addresses checked size, addresses, both rectangles, and clip restoration: nine parameter controls total.
- Three odd-width controls left only the 10-word preparation list and generated no conversion draw. Invalid SRAM length/address/zero size were rejected nine times at helper boundary. This is not evidence of original GPU error handling.

Private evidence: `simulator/gpu-packing-source-01/verification-report.json`, `verify.py`, original probes, and analyzer copy from that time. First verifier assertion incorrectly expected 14 static calls; it was corrected after confirming 15 actual calls, and the earlier script preserved diagnostically. Firmware and execution branches were unchanged.

Public helper reproduction calls `original_packing_commands(raw, full_native_sram, source_address, destination_address, width, height)` in the existing Python environment. Verification of native captures/pinned bundle and actual address extraction is preserved in the private verifier. Next execution uses a new private folder without overwriting existing outputs.

## Next verification and completion boundary

CPU path producing shaders is established, but which nibble GPU reads first for A4/L4, matrix pixel-center rule, AL44 channel layout, and storage quantization remain unverified. A white-dot screen whose adjacent source bytes are identical cannot decide these. Alternating nibbles, gradients, nonzero padding, boundary inputs, and explicit reference rules/limits are needed. Do not add a host packing formula to the consumer without this evidence.

The follow-up unit must verify sampling/storage contracts and failure controls under this source contract, then judge actual guest display buffer → original completion/wait → frame wrapper. Afterwards return to natural IMU/device-input path. GPU model, native execution, and natural main baseline were unchanged here. Overall 3/16, API checklist 3/6, M5 partial remain.

Follow-up [sampling source comparison](gpu-sampling-source-boundaries.md) found a bit-29 wording difference between official VG1000 material and Apollo headers. Another IP's documentation is not treated as Apollo half-pixel verification; inputs distinguishing eight hypotheses were prepared. No GPU pixel-execution evidence was added.
