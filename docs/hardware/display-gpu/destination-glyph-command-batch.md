# Combining output target and glyph in original command list

Follow-up bw256 found missing Nema global SRAM in the 2.4 standalone fixture. The 50-word result below is preserved for that input; current baseline with original main state is 42 words for all three. New batches require canonical Nema region checks. See [correction and reproduction](nema-blend-state-contract.md).

bw-0254 connected output target, clip, and list end to [full letter return](glyph-itcm-read-contract.md). On Renode M55 **five original functions were called and returned sequentially, creating a RAM command list containing both output target and glyph**. The list was not submitted to GPU or executed as pixels.

## Executed flow

1. Original command-list bind.
2. Original destination texture binding.
3. Original clip setup.
4. Full original generic letter call and internal Ambiq/raw bitmap/helper/release.
5. Original command-list unbind and end marker.

Output surface is synthetic address 0x2100a000, 64×32, format 9, stride 64, separate from existing glyph temporary buffer. Clip input is LVGL area `[0,0,63,31]`. Panel specification, actual GPU bus accessibility, and G2 actual allocation addresses were not confirmed.

Pinned [Nema graphics header](https://github.com/lvgl/lvgl/blob/cff1c632206a267534102ee1065f51ac87be4099/libs/nema_gfx/include/cortex_m55_m7/nema_graphics.h) declares format 9 L8 and 0x34 source-only A4, corresponding to target/source formats original functions wrote. Pinned [Ambiq register header](https://github.com/AmbiqMicro/ambiqhal_ambiq/blob/d3278ec49a534728384537557dd44b205ec72129/components/graphics/NemaGFX_SDK/headers/NemaGFX/Nema/nema_regs.h) defines TEX0 base/format-stride/size as 0/4/8 and TEX1 as 0x10/0x14/0x18. These public-name correspondences do not verify shader ISA or actual rasterization.

## Original code results

| Input | Command payload words | Words including end marker | Five calls |
| --- | ---: | ---: | --- |
| Stock 2.4 | 50 | 52 | All returned normally |
| Stock 2.3 | 42 | 44 | All returned normally |
| Faceclaw38 | 42 | 44 | All returned normally |

First six words are target address, format/stride, and size; next four are clip setup. Remaining 40/32/32 words match earlier original A glyph commands. Unbind writes `[0x50000,0]` after payload and disconnects current list. This original function's offset remains at payload length even after writing end marker. Do not confuse offset with total stored bytes or actual GPU-consumed size.

Clip callee stores `x+width`, `y+height`, so this CLIPMAX word is 0x00200040. Initial check wrongly assumed last-pixel coordinates 63/31 were stored unchanged and failed; only the check was corrected after inspecting original instructions. Register names alone do not establish inclusive/exclusive raster boundaries.

An additional stride-80 test changed only one target format/stride word; other commands and call results matched. Both strides left output surface and 32-byte guards before/after unchanged; no claim that CPU drew pixels. Separate existing single-letter function control continued returning 40 words.

## Role of small ARM test caller

`prepare_draw_command_batch.py` executes the same five original functions in Unicorn M7 using pinned inputs to create reference words and phase results. `run_ambiq_glyph_m55.py` compares verified function addresses/arguments and identical memory material on M55.

Initially host stopped/resumed CPU after each function return and set next entry. Stock 2.3 stopped progressing mid-letter after first three functions returned. Additional observation showed no CPU halt, architecture fault, or range violation; observation window ended at same PC/instruction offset. Execution handle ended and container removed. This result and undetermined cause were preserved. Time was not extended or firmware branches changed to pass.

Canonical method uses a **small ARM test caller** without intermediate CPU stops. It has no drawing logic: only AAPCS argument setup → BLX to original address → progress marker after actual return. Five BLXs and binary/ELF/assembly/disassembly/compiler command were preserved. SP and R4–R11 for each return are recorded in markers. Only at end does it move to existing test-exit address.

This does not modify original firmware, nor is execution naturally reached from original main reset or actual RTOS/UI path. Only test caller is placed in dedicated WORK code area. Guest executable range is limited to original main and at most 4 KiB of that caller. Existing single-function mode is separately retained and controlled. Completion of the same functions/arguments in this method does not prove detailed cause of the host-switch method's stop.

## Evidence and reproduction

Final material outside Git:

- `draw-command-batch-inputs-02`: three M7 references and inputs for stride64.
- `draw-command-batch-m55-04/*`: canonical sequential M55 calls for three images.
- `draw-command-batch-padded-inputs-01`, `draw-command-batch-padded-m55-01`: stride80 reference/M55 control.
- `draw-command-batch-single-control-01`: existing single-function control.
- `draw-command-batch-source-01`: pinned public API headers and hashes.
- `draw-command-batch-verification-01/audit.py`, `report.json`: **134 checks** of actual native logs, ELF/code/input hashes, original arguments/full word order, returns/list end/surface boundaries/stride controls.

Four canonical M55 batches and one single control. Earlier `m55-01` host-switch success, `m55-02` and `m55-diagnostic-01` incomplete, and first ARM caller test `m55-03` are separately preserved. Final matrix compared the final caller, including pinned ELF/assembly/disassembly, across three images. Python compile passed and no work container remained.

```sh
python tools/prepare_draw_command_batch.py <simulator> <glyph-captures> <new-batch-inputs>
python tools/run_ambiq_glyph_m55.py <simulator> <new-batch-inputs> <new-native-output> --kind full-letter --canonical-itcm
```

## Remaining connections

Current artifact is a CPU-generated command list with target, glyph, clip, and end information. GPU ring submission, command interpretation, shader/ROP effects, completion IRQ, cache coherency, framebuffer pixels, and viewer are not yet connected. Next inspect existing Nema execution/simulation tools and public command/shader material to define implementable scope. Do not report unsupported commands as successful.

Full-main SPI boundary and normal external font-bank, plus web installation/recovery conditions remain incomplete. Product 13/29=44.8%, scope v2. No glasses, case, or actual persistent-storage access.
