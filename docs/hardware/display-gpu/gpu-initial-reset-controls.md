# GPU initial reset controls and unknown boundary

Status: 15 synthetic conditions, public source offsets, and four actual main conditions observed. Full boot, GPU command execution, integrated screen, and physical verification remain incomplete.

## Source-confirmed meaning

Pinned public GPU metadata describes 0xe8 write as command-list processor reset, 0xfc write as GPU reset. The 0xfc description retains a CHECK address comment. Fixed GPU_Type CMDLISTSTATUS/SYSCLEAR offsets were confirmed by ARM C compilation. This checks register layout/wording, not hardware proof of actual reset extent, timing, or register retention.

`init_nema_regs` in pinned ARM archive writes e8=0, fc=0, 388=1 in order. The same order appears in actual firmware code after ID comparison. Initial ring configuration occurs first, but that alone does not establish actual ring validity after reset. 0x388 was not defined in current pinned public GPU metadata and remains blocked.

## Limited initial-state model

`--gpu-initial-resets` requires source-reset ID response. After shared GPU power on, three ring-configuration stages, and ID read, it accepts e8 DWORD 0 → fc DWORD 0 once each in order. Current model has no state with GPU commands executing or submission allowed, so this applies only to initial quiescent state.

Reset count is the number of accepted initial reset requests/events. It does not implement reset propagation for active GPU work, shader/rasterizer state, DMA, or all internal registers. Repetition, wrong order, nonzero values, partial writes, status reads, access before ID read, and unconfirmed 388 write are blocked.

From first reset, `ring_requires_revalidation=true`. Existing ring values remain only as CPU-written records and addresses for host snapshots, not valid GPU binding/ready; records alone execute no commands. No GPU status, completion ID, or IRQ is generated.

This is not replaced by a no-op ignoring public descriptions or a claim that all GPU internal state reset correctly. Ring preservation/revalidation assumptions after reset require separate review before decoder integration.

## Evidence

`gpu-initial-controls-source-01/report.json`: pinned header/metadata, compiled ID/e8/fc offsets, and ID comparison in three firmware images. Previous ID-read stop report reused as static anchor. `gpu-reset-native-01/report.json`: 11 new conditions (two progress/nine blocked) and four existing-behavior regressions.

Physical glasses, bootloader, OTA, and persistent storage were unchanged. This GPU internal reset model is not evidence of glasses recovery or stock restoration.

## Actual main observations

Three stock 2.3, 2.4, and Faceclaw LP/source-reset runs accepted the two initial requests in order and stopped at 0x40090388 DWORD 1 write with `ring_requires_revalidation=true`. Writer PC is stock 2.3/CFW 0x530054, stock 2.4 0x560f68. This confirms initial request order accepted by the limited model, not actual internal GPU reset success.

Stock 2.4 LP/stuck-off had zero requests, revalidation=false, and was blocked at earlier 0x400900f8. Selecting absent ID with this model is rejected before input-file/Docker access; no absent main-run result is claimed here.

Native/main source snapshots matched current files; nine groups of prior power, ID initialization, ID response, IRQ, HAL, buck, GFX, MCU clock, and memory state plus host ring contents matched prior report in four runs. Preserved host ring contents do not prove GPU binding validity. Preserved in `gpu-reset-verification-01/` final-verification.json, cli-absent-rejection.json, and trail-audit.json.

HP, new Python behavior, active GPU reset, physical recovery, full boot, and screen remain unverified. Next identify actual 0x388 definition and post-reset configuration preservation/revalidation conditions from source and command-generation path. Do not pass undocumented writes as general storage or complete GPU work.

## Follow-up SDK definition

[Official Nema definition research](gpu-extension-register-research.md) identified 0x388 as NEMA_RAST_BYPASS. The earlier undefined notation refers to the prior pinned GPU metadata's scope, not absence of a new SDK definition. Effect of value 1 and reset retention remain undetermined.
