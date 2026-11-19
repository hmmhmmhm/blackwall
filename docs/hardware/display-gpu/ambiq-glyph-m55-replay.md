# Renode M55 comparison of original glyph commands

bw-0250 replayed inputs from [Unicorn glyph-helper tests](ambiq-glyph-draw-commands.md) on Renode 1.17 Cortex-M55. **Nine helpers returned normally and all command words matched.** Separate full generic letter functions in all three images were stopped by the inspector at the same PC/address as the earlier null-buffer read. GPU execution, full main boot, and screen output remain incomplete.

Follow-up bw253 found missing ITCM mapping in this standalone fixture. Under a separate canonical ITCM profile the full letter function returned normally in all three images. The failure below is historical for the then-strict fixture; also read [ITCM follow-up](glyph-itcm-read-contract.md).

## Inputs and execution

`inspect_ambiq_glyph_commands.py --capture` saves SRAM, WORK, R0–R12/SP/LR/XPSR/FPSCR, and S0–S31 immediately before helper entry after original descriptor/bitmap lookup and list bind. Full letter function input is separately saved immediately before its entry. Nine existing results and three failures were compared against canonical results before export was added.

`tools/run_ambiq_glyph_m55.py` checks pinned bundle and snapshot SHAs and loads original ARM main at original address. No reimplemented glyph function or successful-return stub. Each starts at function entry PC, arguments, stack, and synthetic Nema state, so **this is not execution naturally reached from main reset.** Existing reset-run evidence is not replaced by this function test.

Pinned Docker image `sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649` was used without network/device mounts. Inputs mounted read-only; only final virtual-memory copies saved to dedicated output mount. Runs were sequential and tool removed each container.

M55 enabled FPU access, CONTROL.FPCA=1, VPR=0, and defaults for interrupt masks/stack limits. S registers/FPSCR were set from capture. This explicit function-test profile does not claim all CPU/exception states are identical between M7 and M55.

## Results

| Input | Words each for A/W/g | Return and callee-saved registers/SP | Full letter null-read PC |
| --- | ---: | --- | --- |
| Stock 2.4 | 40 | Match | 0x4d9e78 |
| Stock 2.3 | 32 | Match | 0x4c6638 |
| Faceclaw38 | 32 | Match | 0x4c6638 |

All nine helpers' source pointer/format/stride/size, conversion matrix/area/draw commands matched Unicorn in **full order and values**. Snapshot SRAM and pixel buffers stayed unchanged; final WORK changes stayed within declared unit state, command list, descriptor, and stack ranges. GPU did not execute commands or change framebuffer pixels.

An observer-off stock 2.4 A control was added. Same input snapshot/fixture source, return registers, final SRAM/WORK hashes, and command words matched observer-on. This single-condition control is not general proof for every observer/function.

## Meaning of null-buffer boundary

`tools/renode-arm-function-fixture.cs` observes original execution/memory ranges and stops at original return boundary. Out-of-range access is recorded and stopped without replacing opcodes, branches, or returns.

In three full-letter conditions original `ldr.w sb, [r5, #0x10]` with R5=0 attempted a four-byte read at address 0x10. Renode bus warned no peripheral existed there; memory observer aborted CPU at the same access. Observer notification occurs after bus read, so do not say it was blocked before the invalid bus read. No subsequent guest instruction was allowed to proceed.

CFSR/HFSR were 0. This is **reproduction of the exact null-access point and inspector stop**, not reproduction of an actual G2 HardFault/device defect. Actual main font selection and post-snapshot initialization remained to be investigated. Neither buffer nor original function was patched into success.

## Execution record and verification

Canonical material outside Git:

- `ambiq-glyph-captures-01`: 12 function input snapshots and comparison to existing results.
- `ambiq-glyph-m55-03/stock24-glyph-*`: three stock 2.4 helpers.
- `ambiq-glyph-m55-04/stock24-full-letter`: stock 2.4 null read.
- `ambiq-glyph-m55-05`: six stock 2.3/Faceclaw helpers and two null reads.
- `ambiq-glyph-m55-06`: one observer-off control.
- `ambiq-glyph-m55-verification-01/audit.py` and `report.json`: **285 saved-audit checks**.

Audit checks actual native logs/final memory, input snapshot/original/source hashes, existing command words, returns, null access, and observer control. It evidences nine normal helpers + three expected null boundaries + one observer control. Python compile passed.

Earlier `m55-01` was rejected by inspector on instruction fetch at return-sentinel address. `-02` explicitly permitted return-address read range and same helper returned normally. Full matrix `-03` passed three stock 2.4 helpers but stopped because null bus warning was absent from expected list. Without overwriting raw failure, only exact PC/address/width/warning was classified as expected boundary and reverified in `-04`. Original firmware/function arguments were unchanged. A in `-02` was repeated in matrix `-03` for full matrix verification, not added as separate product completion.

Next establish full letter-path inputs by identifying actual UI font/callback selection and initialization contract. GPU command interpretation/execution and integrated main/screen must then connect. Remaining web installation/independent recovery integration conditions remain. Product fulfillment 13/29=44.8%, scope v2. No glasses, case, or actual persistent-storage access.
