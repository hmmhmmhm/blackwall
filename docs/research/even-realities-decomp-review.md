# Even Realities G1 Decompilation Reference Review

Conclusion: **This is useful supporting material for analysis of the panel, display data, and app behavior. It is not a replacement foundation for a G2 chipset emulator or installation and recovery implementation.** At the user's request, the actual files were read and compared against pinned G2 sources.

## Pinned sources

- Repository: [JohnRThomas/even_realities_decomp](https://github.com/JohnRThomas/even_realities_decomp), commit `f571782aedb6fdefbcbfe2a4d1e309bb47143581`.
- Of 2,529 files in the complete tree, 38 relevant files were extracted for reading. The source archive SHA-256 and each file's SHA-256/Git blob were retained in private `simulator/even-decomp-research-01/sources.json`. Upstream scripts, build commands, and installation commands were not run.
- G2 sources compared: `patches/panel.c`, `draw.c`, and `zlib_glue.c` from g2flash commit `845f665e0dfdcfd06b7d3a294388de6f17a5bd59`. The three working files were directly compared with `git show <commit>:<path>` bytes, and SHA-256/Git blobs were recorded. These are upstream G2 analysis and implementation sources, not physical-device validation in this investigation.
- `tools/inspect_even_decomp_references.py` checked file integrity and 62 key source observations below. Results are in private `simulator/even-decomp-verification-02/report.json`. After review, the initial 59 checks, which checked only G2 HEAD, were supplemented with commit-byte comparisons for all three files. The initial evidence was also retained.

## Target differences

The [README](https://github.com/JohnRThomas/even_realities_decomp/blob/f571782aedb6fdefbcbfe2a4d1e309bb47143581/README.md) identifies this as a G1 decompilation project. Its [analysis workflow](https://github.com/JohnRThomas/even_realities_decomp/blob/f571782aedb6fdefbcbfe2a4d1e309bb47143581/helpers/ai/function_discovery_workflow.md) describes G1 1.63, nRF5340, and Zephyr/NCS 2.5.1. These differ from our G2 Apollo510/M55 and 2.3/2.4 binaries. A G1 original binary was not independently obtained, executed, or checked for equivalence.

Do not copy function names, addresses, struct offsets, SPI peripherals, IRQs, boot order, or OTA behavior into the G2 model. In particular, the README's nRF5340 DFU example is not evidence for a G2 web installation or recovery procedure.

## Immediately useful references

| Source | Observed in source | Blackwall use |
| --- | --- | --- |
| `jdb013vga/jbd013_api.h` and G2 `panel.c` | Matching command values for sync `97`, display enable `A3`, write enable `06`, status read `05/35`, luminance read `37`, current read `47`, and ID read `9F` | Search list for future interpretation of G2 MSPI traffic and analysis of panel peer candidates. Not proof of the same wire protocol or peer |
| `gui_bitmap_draw.c` | Path expands 1-bit input into luminance nibbles and stores two pixels per byte | Comparison candidate for G2 framebuffer pixel order and stride; compare independently with existing G2 `draw.c` |
| `_reflash_fb_data_to_lcd.c` | Row stride 320, transfer header containing coordinates, and sync 97 candidate | Search for original G2 functions and transfer boundaries. Do not port G1 addresses or update ranges |
| `display_dispatch_thread.c`, `display_thread_handler.c`, etc. | Decompiler representations of display task and event handling | Clues for finding similar G2 logs, functions, and queue ownership |
| `ble_process_req_dispatch.c`, `ble_process_put_req.c`, `ble_process_get_req.c` | Candidate G1 request dispatch and notification/app feature handling | Conceptual comparison for official-app data flow research. G2 message numbers, services, and payload compatibility remain unverified |
| Ghidra analysis workflow | Function identification by comparing log strings, callees, structures, and actual SDK sources | Supporting technique for current G2 exact-image static analysis. Do not automatically register upstream names as correct |

The existing independent ARM renderer uses a 576×288 test screen. In contrast, the pinned G2 g2flash raw panel definition is 640×480, stride 320, packed 4bpp. Do not treat these as the same framebuffer contract. For an integrated screen, first observe the actual G2 original buffer, stride, and transfer coordinates. G1 reference panel code also handles 640×480, but that alone does not establish the G2 visible area or crop.

## Quality and reuse limitations

- G1 `read_id()` reads three bytes; G2 `panel_poke()` reads four. A common opcode alone does not justify copying the response length.
- `src/app/jdb013vga/hal_driver.c` is a Linux spidev example. `spi_tx_frame()` calculates transfer length using `sizeof(param)`, but `param` is a pointer, so this is not the actual payload length. Do not adopt this code as a G2 driver or a reliable protocol test tool.
- The current `CMakeLists.txt` specifies only `sample_main.c` as a build target. Do not interpret this as verification of a working firmware build linking all the decompiled functions. The README's function-labeling progress is not execution accuracy or a reconstruction success rate.
- `helpers/ai/memory_map.md` has a table classifying even MMIO address ranges as RAM. Do not use it as the G2 memory/peripheral map. Distinguish AI-assisted analysis, actual expressions in individual C files, and evidence from original G2 execution.
- No root LICENSE/COPYING/NOTICE applying to the entire repository was found in the tree. Do not extend CMake SPDX identifiers or the ST25DV subdirectory license to the whole decompilation. For now, cite the source and use it as an analysis lead without copying code.

## Application to current work

In the MSPI1 configuration execution, the next stop is a CQ index write. Add the panel commands above to the candidate list, but **do not assert that the current MSPI1 peer is the panel**. The previous G2 panel handle slot and this runtime slot remain different. First model CQ/PIO/DMA initiation and capture actual original requests; then compare them with panel commands.

This review did not change hardware compatibility or installation readiness assessments. No physical-device access, bootloader/firmware write, or Astra execution occurred. Full boot, screen output, and recovery remained unverified, and overall product progress remained 13/29, 44.8%.
