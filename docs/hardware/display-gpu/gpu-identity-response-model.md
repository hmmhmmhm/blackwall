# GPU fixed-ID comparison and virtual response

Status: source, static three-input, 12 synthetic-condition, and five actual-main-condition verification complete. Full boot, GPU execution, integrated screen, and physical verification remain incomplete.

## Evidence

Pinned Apollo510 GPU metadata lists fixed IDREG 0x1ec value 0x86362000. `tools/analyze_gpu_identity.py` pins public header/metadata hashes and confirms GPU_Type.IDREG offset 0x1ec via ARM C compilation. It locates static call candidates connected to actual ID-read stop PCs in three pinned firmware images and confirms comparison against PC-relative literal 0x86362000.

This is fixed GPU-presence comparison rather than per-bit capability negotiation. Code subsequently writes an error flag on mismatch, but this static pattern alone does not prove the full failure path or safe fallback. The archive's `nema_init` and `nema_checkGPUPresence` also contain the constant. This does not claim restored function symbols or exact firmware SDK version.

## Optional response

`--gpu-identity-response source-reset|absent` requires initial ring configuration. Once shared GPU power is on and all three ring-configuration stages complete, it supplies these values on IDREG DWORD read:

- source-reset: 0x86362000, used by both public metadata and firmware.
- absent: explicit negative-test 0, not a physical hardware reading.

Default is unsupported guard. Writes, partial reads, adjacent registers, and reads before configuration remain blocked. Fixed ID response is not evidence of GPU engine, render capability, completion interrupts, performance, or physical compatibility. Matching this value does not complete unimplemented commands.

Static evidence: `gpu-identity-analysis-01/report.json`, compilation input/output and compiler.log. Pinned upstream material is listed in [GPU upstream snapshot](../../data/gpu-upstream-snapshot.json). No new GPU driver/library was installed on glasses and firmware/bootloader/OTA were unchanged.

Static analysis and offset compilation were completed before connecting the model. Subsequent GPU writes remain guarded so permitting ID read does not substitute for full capability or work completion.

## Execution results and limits

`gpu-identity-native-01/report.json` passed eight new conditions (three responses/five blocks) and four existing-behavior regressions. It distinguishes fixed ID, repeated read, absent 0, and blocks writes, partial reads, preconfiguration, adjacent addresses, and option disabled. Static analyzer also rejected three cases: wrong main hash, read boundary, and unknown input. This is not exhaustive input verification or actual hardware testing.

Three stock 2.3, 2.4, and Faceclaw LP/source-reset runs read ID once and stopped at GPU 0x400900e8 DWORD 0 write. Writer PC is stock 2.3/CFW 0x530054, stock 2.4 0x560f68. This is the next initialization access, not successful GPU commands or screen output.

Stock 2.4 LP/absent read 0 once then stopped at GPU 0x400900fc read. This observes another GPU access after mismatch, not proven safe fallback/recovery. Stock 2.4 LP/stuck-off read ID zero times and was blocked at prior 0x400900f8 write.

Native/main source snapshot match and power, ID initialization, IRQ, HAL, buck, GFX, MCU clock, and memory state of source-reset 3/stuck-off 1 were checked against prior report. Absent's extra path is separate observation and is not claimed state-identical. Evidence is preserved in `gpu-identity-verification-01/` final-verification.json, analysis-boundaries.json, and trail-audit.json.

HP, new Python response, physical GPU, command completion, and full boot were not verified at this stage. Next compare side effects of normal-path 0xe8 and subsequent initialization controls, then connect decoder without treating unsupported GPU work as successful.
