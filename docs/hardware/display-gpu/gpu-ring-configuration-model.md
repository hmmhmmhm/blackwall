# Initial GPU ring configuration model

Status: 21 synthetic conditions and four actual main conditions observed. Full boot, GPU command execution, integrated screen, and physical verification remain incomplete.

## Model scope and assumptions

`--gpu-ring-configuration` requires the initial ID0 model. After shared GPU power is on and ID0 initialization completes, it stores these three DWORD writes once each in order:

1. 0x400900ec: low three bits=6, remainder an 8-byte-aligned SRAM address.
2. 0x400900f0: base equal to first address.
3. 0x400900f4: byte length, 16–65536, multiple of 16, with base+length within virtual SRAM.

SRAM range is 0x20000000–0x20380000. Length limits are simulator policy including initial ring footer, not hardware minimum/maximum. Length observed in actual firmware is 4864. Basis: [actual ring candidate capture](gpu-id-initialization-capture.md) and pinned library initialization sequence. This model is a configuration latch; it does not check guest allocation, footer, or valid commands or execute DMA. Even after three stages it does not declare GPU initialization/ready/command completion.

Reads, partial writes, wrong order/flags, base mismatch, length errors, SRAM overflow, repeated setup, and new ring submissions stop at guards. ID read/increment and completion interrupts remain unsupported. Other GPU writes are not treated as general storage. Watchdog high guard uses existing shared GPU owner to retain power/ID/ring state together.

This configuration latch does not replace a full GPU decoder. Observe the next actual command list and connect initial configuration separately from submission/execution. No physical connection, installation, OTA, or persistent writes.

## Verification and actual execution boundary

`gpu-ring-native-01/report.json` passed 17 new conditions (three normal/14 blocked) and four existing-behavior regressions. It distinguishes normal/minimum/maximum lengths, order, flags, addresses, base relationships, length, overflow, reads, repetition, submission, partial writes, access before ID, and disabled option.

Three stock 2.3, 2.4, and Faceclaw LP/active runs passed three setup stages and stopped at next GPU 0x400901ec DWORD read. Pinned public GPU metadata calls it IDREG. No arbitrary value was supplied. Read-helper PC: stock 2.3/CFW 0x53004a, stock 2.4 0x560f5e.

After CPU stop, entire configured ring range was preserved as host snapshot. Each is 1216 words: first 1212 are 0, last four `[0xff0000f0, base, 0xff0000f4, 4864]`. This observes only initial footer, not a user-screen command list or GPU execution. Snapshot is read only after rechecking 8-byte-aligned base, length multiple of 16, 16–65536 bytes, and SRAM extent. It is mapped-SRAM observation, not allocation-validity verification.

Stock 2.4 LP/stuck-off had zero setup stages, no snapshot, and was blocked at earlier GPU 0x400900f8 write. This simulator rejection does not prove firmware fallback/recovery. HP, new Python stage, and GPU IRQ generation were not verified here.

Final C# snapshot and combined main source matched current files; power, ID, IRQ, HAL, buck, GFX, MCU clock, and memory state of four main runs matched previous-stage report. Results preserved in `gpu-ring-verification-01/final-verification.json` and `trail-audit.json`.

Next compare actual ID-read consumer, required capability, and command-generation code. Do not fill unknown ID with success or complete unsupported GPU commands.
