# Limited recording of raster initial value and subsequent boundary

Status: 13 synthetic conditions, four main conditions, and initial command-prefix analysis for three inputs completed. Full boot, screen, and GPU execution remain incomplete.

## Confirmed and unknown effects

Official pinned header defines 0x388 as NEMA_RAST_BYPASS. Search for explicit `mov r0,#0x388` uses in the pinned archive found value-1 write in init_nema_regs. This does not prove absence of indirect address calculations or uses in all other archives. SDK then proceeds to IRQ control and blender/fragment-shader initialization. Bitwise rendering effects of value 1 remain unimplemented.

A separate TikuOS Apollo510 driver describes value 1 as direct DRAW-path initialization and uses the same e8/fc/388 order. This is that developer's implementation/description, not physical-device evidence checked here. Blackwall GPU rendering behavior was not adopted from that description alone.

## Optional trace-only storage

`--gpu-raster-init-storage` requires initial reset controls. After shared GPU power on and two reset-request stages, it records one 0x388 DWORD 1. It supplies neither read value nor rendering side effects. Reports explicitly say trace_only=true, rendering_effect_implemented=false.

Zero, other values, repetition, before-reset access, reads, partial writes, and neighboring registers are blocked. Default stops at 0x388 write as before. This optional observation path does not fully model GPU or verify initialization success. Subsequent shaders, draws, and actual commands remain guarded as unsupported.

`ring_requires_revalidation=true` remains after reset. Stored value does not create completion ID, ready, or IRQ, nor establish valid ring binding. Additional progress on this path is not a substitute for boot/integrated-screen completion.

## Verification

`gpu-raster-native-01/report.json` passed nine new conditions (one recorded/eight blocked) and four existing-behavior regressions, including prior default block at 0x388.

No glasses connection, physical RAM execution, flash, OTA, or persistent writes.

## Next state captured in actual main

Observation mode for stock 2.3, 2.4, and Faceclaw LP recorded initial value 1 then stopped at GPU CONFIG 0x400901f0 DWORD read. Model IRQ-clear count remained 1; no additional shader-related MMIO write was accepted. Stock 2.4 stuck-off saved no value and stopped at earlier f8.

Host ring differed from before: 35 words changed in first 50 for all three inputs. Initial prefix matches these 25 register/data-pair candidates:

- 0 to NEMA_INTERRUPT (0xf8).
- Three pairs each of NEMA_IMEM_ADDR (0xc4) and data registers 0xc8/0xcc for slots 24–31.
- Slot 24–30 data 0; slot 31 register 0xc8 word 0x08000002, 0xcc word 0x80000009.

This observes CPU preparing command data in RAM, not GPU execution of upload, shader, or IRQ control. 64-bit instruction interpretation and color effects were not verified. Producer pointer/valid submission length were not observed, so 25 pairs are not established as actual submit length or entire command list. Remaining zeros do not prove absence of valid commands.

Initial verification assumption that previous ring contents remained unchanged failed. The explanation based on MMIO boundary alone that CONFIG lookup preceded shader preparation was corrected to distinguish RAM queue preparation from actual GPU access. Original runtime report was unchanged; snapshot differences analyzed without rerun. Ten controller groups matched previous, while 35 changed RAM-ring words were separately preserved.

`tools/analyze_gpu_pending_init.py` compares pinned bundle/main hashes and first 50-word pattern only for this observation stage. It is not a general GPU decoder or shader executor. Three inputs passed; four mutations of shader word, register offset, trace label, and main hash were rejected. Final evidence is analysis 02 adding main-hash checks after 01.

Execution/analysis results are preserved in private gpu-raster-verification-01 final-verification.json, preverification-correction.json, packet-analysis-negatives.json, and trail-audit.json. TikuOS source was separately preserved in gpu-raster-research-01 with commit, Git blob, and SHA, not executed or adopted. Public-source developer claims and physical evidence are distinct.

Next identify CONFIG-required capabilities and actual producer/submission range of pending commands, then connect a supportable packet decoder and command-processing model. Observation-mode progress is not promoted to normal GPU behavior or full boot/screen verification. HP and new Python behavior remain unverified.

Additional reference implementation: [pinned TikuOS driver](https://github.com/tikuos/tikuOS/blob/39ad38c9407ca1b206364e64cdac87b0d8ac7980/arch/ambiq/tiku_gpu_arch.c).
