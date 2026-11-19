# Original letter call with an ITCM read

bw-0253 reverified the complete original generic letter function under a separate profile that fixes the [missing ITCM in the isolated fixture](draw-unit-selection.md). **On Renode M55, stock 2.4, stock 2.3, and Faceclaw38 all returned normally from the complete function for character A and wrote the same 40/32/32 words as the earlier helper.** Original functions, branches, and returns were not changed. GPU execution, framebuffer pixels, and full main screen output remain incomplete.

## Original data flow checked first

The earlier read at address 0x10 is `ldr.w sb, [r5, #0x10]` in the bitmap callback. This instruction does not change flags. If `req_raw_bitmap` bit 0 is 1 in the original descriptor and the glyph ID is nonzero, the subsequent raw-bitmap path calculates and returns a ROM bitmap pointer. On this path the newly read SB value is not used, and the epilogue restores the pre-call SB from the stack.

`inspect_glyph_itcm_read.py` checks conditional branches, instruction order, and register reads/writes in the three pinned originals. It confirms that the raw path neither consumes SB nor calls another function, and that the final pop restores SB and PC. This conclusion is **conditional on the read completing**. The fact that the value is unused does not establish that an actual bus fault or memory power state is harmless. It is not generalized to decompression paths or arbitrary callbacks.

In a separate value comparison, the null address was not mapped. We changed the data word of a valid caller-owned draw buffer to `0`, `ffffffff`, `a5a5a5a5`, `12345678`, `80000000`, and `1`, then ran the original descriptor/bitmap wrapper. A/W/g × six values × three images gives 54 bitmap calls and nine descriptor calls. Return pointers, all output GPRs, and stack hashes were identical across values. This supports the original data flow above; it is not a dynamic enumeration of all 32-bit values.

## ITCM data matching integrated main

The integrated main maps ITCM from address 0 to 0x40000, but the earlier isolated function fixture lacked this region. The new `--canonical-itcm` profile checks the pinned input, report, and main SHA from the existing `em9305-reset-main-01/<case>`, and applies the 256-byte prefix observed when the original main stopped to the original ITCM fill. The value at address 0x10 is the virtual fill `a5a5a5a5`, not a value read from a real device.

The original function fixture's strict default behavior remains. Even in the opt-in profile, only one kind of read is allowed under these conditions:

- The verified PC of the relevant original bitmap callback
- Address 0x10, width 4 bytes, R5=0
- Descriptor in the specified WORK, raw bit 0=1, and nonzero glyph ID

Other low-memory access and ITCM writes/execution are not allowed. The CPU load reads actual mapped memory; the observer does not change the opcode, PC, or load result. Future runners must recheck the original raw-path contract before configuring this profile. They reject it if changed original code no longer satisfies these conditions.

## Complete M55 function results

The task/layer/unit, reused buffer, and Nema list from the existing full-letter entry snapshot were unchanged. This does not mean the source image and the complete naturally reached state after main reset are the same; function arguments and FPU profile remain explicit synthetic inputs.

| Input | Complete letter return | Instruction words | Relevant ITCM reads |
| --- | --- | ---: | ---: |
| Stock 2.4 | Normal | 40 | 1 |
| Stock 2.3 | Normal | 32 | 1 |
| Faceclaw38 | Normal | 32 | 1 |

The original internal calls generic descriptor → reshape → Ambiq callback → raw bitmap → glyph helper → release ran to completion. The commands matched every word of the earlier original A helper, and callee-saved GPRs/SP were restored. Virtual SRAM and the pixel buffer were unchanged, and final WORK changes stayed within the specified object, header, list, and stack ranges. This sample of the complete call is character A; it does not claim that all nine helpers were run as complete letter calls.

Two controls were also run. The new fixture in default strict mode continued to stop at the same address 0x10 boundary as before. An **explicit counterfactual test** changing only the relevant ITCM word to 0 in the complete stock 2.4 function also returned normally, with command, return GPR, and final SRAM/WORK hashes equal to the canonical A5 test. This does not assume the actual word is 0.

The earlier failure is therefore explained by a missing memory map in this function fixture. It is not evidence that the actual firmware needs modification, and no firmware patch was made. This test also does not establish readability on an actual device under other memory power, alias, or security conditions.

## Evidence and next steps

Canonical artifacts outside Git:

- `glyph-itcm-read-contract-01`: original register/branch contract and 54 word comparisons
- `glyph-itcm-m55-01/stock24-full-letter`, `glyph-itcm-m55-02/{stock23,cfw}-full-letter`: the three complete functions
- `glyph-itcm-strict-control-01`: preservation of the default strict boundary
- `glyph-itcm-word-control-01`: counterfactual word-0 control
- `glyph-itcm-verification-01/audit.py`, `report.json`: **176 checks** of original bytes/inputs, data hashes, actual native logs, complete commands, memory, and controls

Three complete-function and two control runs, five native runs total, are preserved. Four unit tests also passed to verify rejection when the original contract changes. The protection offered by the current parser and fixture is distinct from GPU and hardware verification. The earlier missing-mapping failure record was not changed.

The next integration is draw target setup, command submission, GPU effects, and the display buffer. At present the CPU has written commands to RAM; they have not been executed into actual pixels. Remaining integration conditions, including the full main SPI/frontier and a normal external font bank, still apply. Product progress is 13/29=44.8%, scope v2. There is no access to glasses, case, or actual persistent storage.
