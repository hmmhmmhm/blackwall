# GPU ring initialization and register-semantics research

Status: static call-pattern analysis completed for three firmware images. GPU model and actual main execution endpoints remain as before. Full boot, integrated screen, and physical verification remain incomplete.

## Confirmed code and inference

`tools/analyze_gpu_ring_setup.py` checks CRC/hash of three pinned bundles and main hashes, then finds one candidate each with the following order using the writer address from prior initialization report. Candidates come from linear decoding of actual instructions; they are not restored function symbols or proof of full path execution.

| Order | GPU offset | Actual code value | Confirmed scope |
| --- | --- | --- | --- |
| 1 | 0x148 | 0 | Matches actual stop address/value of previous main run |
| 2 | 0xec | word at descriptor+8 OR 6 | Static call argument; actual value/side effects unobserved |
| 3 | 0xf0 | word at descriptor+8 | Static call argument; actual value/side effects unobserved |
| 4 | 0xf4 | word at descriptor+16 | Static call argument; length unit undetermined |

This order also appears in pinned LVGL ARM archive `nema_rb_init` with relocation names. Archive was read with `llvm-objdump -dr`, not executed or linked. Its descriptor layout differs, so ABI or firmware SDK-version identity is not inferred.

## Where public metadata cannot be used unchanged

Pinned Apollo510 GPU documentation labels 0x148 DRAWPT2Z. In contrast, firmware IRQ-handler candidate reads 0x148, clears IRQ, calls with IRQ28 as argument, and rereads/compares 0x148. Official Apollo510 Nema HAL names the corresponding value `NEMA_CLID` and clears NVIC pending too. Firmware's corresponding BL target was not verified here through pending-clear behavior, so inference is distinguished as call-pattern-based. Pinned archive ring initialization/reset writes 0 to 0x148, and command-list submission also reads it.

Thus simply implementing 0x148 as coordinate storage in this path lacks support. Command-list ID is strongly plausible, but this research alone does not establish hardware aliasing or actual register side effects. Future model must state this assumption.

Public documentation names 0xec CMDLISTRINGSTOP/UPDATEPRT, 0xf0 CMDLISTADDR/BASEPTR, and 0xf4 CMDLISTSIZE/LISTWORDS. Yet archive writes original size preserved in `.bss.ring_size_bytes` to 0xf4. Do not assume words from metadata name when reading memory. Actual firmware descriptor length and allocation bounds need separate confirmation.

`nema_rb_submit_cmdlist2` writes words into ring memory, flushes, then writes `(ring_base_phys + index*4) | 4` to 0xec. Thus 0xec must not be treated as side-effect-free storage. Exact hardware meaning of initial OR6 and submit OR4 is not established. Do not invent completion IRQ or CLID increments.

## Next implementation scope

1. Separate observed initial 0 write to 0x148 after power on/idle IRQ clear as an explicit ID-initialization assumption.
2. While blocking next 0xec access, capture actual arguments and ranges of descriptor/ring memory prepared by guest.
3. After identifying allocation, initial ring words, and submission timing, connect decoder. Do not complete unsupported commands.

Do not substitute an independent renderer or LVGL demo for actual main display execution. This research includes no new firmware main run, GPU model change, or physical access.

## Evidence and reproduction

`gpu-ring-signature-01/report.json`: static candidates for three inputs. First tool run failed with zero candidates because slice included the next function's first instruction. Window corrected to 34 bytes and all three analyzed. This was a tool-boundary fix, not firmware behavior or source-image modification.

`gpu-register-map-research-01/lvgl-archive-disassembly.log`: pinned archive static disassembly. Reuses SHA/Git blob from earlier `gpu-initialization-research-01/source-manifest.json`.

```sh
python tools/analyze_gpu_ring_setup.py <private-inputs> \
  <gpu-initialization-signature-03/report.json> <new-private-output>
```

Sources: [pinned Apollo510 HAL](https://github.com/AmbiqMicro/lv_port_ambiq/blob/be2dfdd522f7897c819c422d319d1ee3949fab95/lvgl_ambiq_porting/NemaGFX_hal/apollo510_nemagfx/nema_hal.c), [pinned LVGL tree](https://github.com/lvgl/lvgl/tree/cff1c632206a267534102ee1065f51ac87be4099/libs/nema_gfx), [pinned GPU metadata](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/gpu_regs.html).

Additionally, nema_regs.h and nema_ringbuffer.h were not found in a pinned official STM32CubeU5 tree. This is absence within the searched tree, not a general claim that Nema headers are not public. ST documentation for another chip is not used to prove Apollo510 offsets.

## Follow-up runtime observation

[Initial ID0 and ring candidate capture](gpu-id-initialization-capture.md) confirmed current LP initialization paths of three pinned firmware images match a 4864-byte footer/index relationship. This narrows the previously undetermined unit within that observation scope, not a general guarantee for GPU command execution or other buffers/firmware.
