# Capturing initial GPU ID 0 and ring candidates

Status: 13 synthetic conditions, four actual main conditions, and three snapshot analyses completed. Full boot, integrated screen, and physical verification remain incomplete.

## Explicit model assumption

`--gpu-id-initialization` requires `--gpu-interrupt-clear`. With shared GPU power on and at least one idle IRQ clear processed, it permits one DWORD 0 write to GPU 0x40090148. This assumes command-list ID initialization rather than the public coordinate-register name, based on [static ring research](gpu-ring-setup-research.md). Actual aliasing and physical behavior are unverified.

ID reads, nonzero values, repeated initialization, partial/early access, and ring requests stop at unsupported guards. Permitting initial 0 does not complete commands, increment ID, or generate IRQ. Reset propagation and GPU IRQ-line connection are not implemented.

## Post-stop observations

When the next GPU 0x400900ec DWORD write is blocked by guard, host records candidates based on CPU R4 and R1. R4 is a descriptor candidate in static initialization code; the blocked value with low three bits removed is a ring candidate. No actual GPU DMA executes.

Only aligned fixed lengths within virtual SRAM 0x20000000–0x20380000 are read. Descriptor eight words and ring prefix 16 words are observed; out-of-range candidates remain null without reading. They may include uninitialized SRAM, so values alone do not establish valid buffers. For candidate length fields, tail four words under byte and word interpretations are recorded as separate assumptions. Length is limited to 16–65536 bytes and each 16-byte observation's SRAM bounds rechecked. This does not pre-establish allocation bounds or valid length. Original register values and LR are preserved for comparison with static call sites.

No device connection, physical RAM execution, flash, OTA, or persistent writes occurred.

## Results

`gpu-id-native-01/report.json` passed nine new conditions (one normal/eight blocked) and four existing-behavior regressions. Nonzero value, access before IRQ clear, repeated initialization, ID read, partial write, ring request, stuck-off, and disabled option are blocked. Normal behavior is one initial 0 write only.

Three active runs in `gpu-id-main-{stock23,stock24,cfw}-lp-01/report.json` were blocked at GPU 0x400900ec write after ID initialization. All had low bits=6, descriptor index=1212, candidate length=4864. Captured LR matched next ring-request call in the static initialization candidate.

First 16 ring words are 0; last four under byte-length interpretation are:

```text
0xff0000f0  <ring base>  0xff0000f4  4864
```

This matches pinned archive's initial ring-footer generation code. All four tail words under word interpretation were 0. The relationship byte length 4864 and index=4864/4-4 was observed in three inputs; it does not generally prove all future firmware, ring buffers, allocations, or physical DMA units. This footer is initial ring linkage, not yet a user-screen command list.

`gpu-id-main-stock24-stuck-lp-01/report.json` was not initialized and has no snapshot; it was blocked at earlier GPU 0x400900f8. This simulator guard is not firmware fallback/recovery verification. HP combinations, new Python stage, and GPU IRQ connection were not verified here.

`tools/analyze_gpu_ring_capture.py` compares pinned input hashes, static LR, initialization state, SRAM ranges, request/descriptor relationship, and byte footer. All three inputs passed; four snapshots with bad footer, call address, out-of-SRAM descriptor, or request value were rejected. Runtime evidence/source snapshot checks are preserved in `gpu-id-verification-01/final-verification.json`.

## Next steps

Separate initial ring setup from submission, verify initial structure in known byte ranges, then connect 0xec/0xf0/0xf4 path. Do not complete commands not processed by GPU decoder or increment ID. Actual command list, framebuffer, and display integration remain incomplete.
