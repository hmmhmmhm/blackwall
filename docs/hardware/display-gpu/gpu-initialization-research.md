# GPU initialization evidence and execution backend research

Status: source, static instruction, and synthetic IRQ28 verification completed. No new GPU execution model adopted. Original main's last execution boundary remains GPU.INTERRUPTCTRL (0x400900f8) write. Full boot, integrated screen, and physical verification remain incomplete.

## Initialization behavior confirmed

A unique static pattern in stock 2.3, 2.4, and Faceclaw writes 0 at offset 0xf8 in original main, then configures IRQ28 priority 4 and enables IRQ28. Positive-IRQ branch and literals of call target were also checked: code writes byte 0x40 to NVIC IPR (0xe000e41c) and bit 28 to ISER (0xe000e100). This path was not executed in actual main; analysis used first GPU write PC of existing native runs and bundle/main hashes.

This pattern matches `nema_sys_init` in official [Apollo510 Nema HAL](https://github.com/AmbiqMicro/lv_port_ambiq/blob/be2dfdd522f7897c819c422d319d1ee3949fab95/lvgl_ambiq_porting/NemaGFX_hal/apollo510_nemagfx/nema_hal.c). Official HAL clears IRQ, configures/enables NVIC IRQ28, then prepares ring buffer. Its IRQ handler separately handles IRQ clear and NVIC pending clear. Thus writing 0 is not simply value storage or work completion.

Pinned Apollo510 header GPU_IRQn=28, INTERRUPTCTRL offset 0xf8, and actual MMIO boundary agree. Public header's CHECK address comment prompted the comparison. This does not prove original symbol restoration, exact SDK-version match, or physical GPU behavior.

`tools/analyze_gpu_initialization.py` checks pinned inputs and evidence from six saved native combinations and locates writer/call patterns above. One candidate matched per input. This is linear Thumb decode candidate search, not full function/execution equivalence analysis. Unknown firmware inputs are rejected before decoding.

## Reuse research

Pinned commits and file hashes are recorded in [GPU upstream snapshot](../../data/gpu-upstream-snapshot.json). Materials/libraries remain outside Git and were neither executed nor linked into the project.

| Material | Confirmed | Current judgment |
| --- | --- | --- |
| Official Ambiq LVGL port `be2dfdd522f7897c819c422d319d1ee3949fab95` | Apollo510 HAL, IRQ28, MMIO read/write, FreeRTOS wait, ring-buffer connection | Source reference for initialization/IRQ, not GPU engine |
| LVGL `cff1c632206a267534102ee1065f51ac87be4099` | Nema headers and M55 archive, header API version 1.4.12 | Candidate API/command-generation reference; actual G2 SDK version unknown |
| Zephyr HAL `61b293a49db34030c545f99101f7ebf6a3050314` | GPU register definitions, offsets, field descriptions | Structure/side-effect reference; full actual device state unknown |
| Renode Infrastructure `042a58285ee91453f99d31f19e8aa140102ec540` | STM32DMA2D and PixelManipulationTools converter/blender use | Pixel-processing candidate, not Nema register/command decoder |

Official port separately requires AmbiqSuite. ELF objects in both inspected archives were all ARM (31/27 respectively); after comparison against archive-wide definitions, references to `nema_reg_read/write`, `nema_sys_init`, and IRQ wait functions remained. The HAL providing them waits for GPU MMIO and actual completion interrupts. No GPU execution model directly connectable to Renode was identified in researched material. This does not mean every SDK/commercial model was investigated or no such model exists.

The conclusion that these materials cannot directly serve as a GPU model is an inference based on static analysis and official hardware-acceleration documentation. Executing an API library and executing GPU commands it generates are separate.

STM32DMA2D uses STM32 protocol and cannot be connected as Nema protocol. Its color-conversion/blend portions may be references, but source excludes A4/L4 output. G2 packed 4bpp display path and actual GPU framebuffer format compatibility were not verified. It was identified as a pixel-backend candidate, not executed or adopted here.

Repository-root MIT, HAL BSD-3-Clause, and individual Think Silicon header/source permission notices were recorded. Archive-specific conditions are not determined from root license alone; no binary dependency adopted. Full upstream projects and proprietary firmware were not copied into this repository.

## IRQ28 core verification

In `gpu-irq28-core-smoke-01/report.json`, M55 recorded pending=1 while IRQ28 disabled, pending=0 after clear, and exception 44 (16+28) entry and one handler call after enable/pending. Existing MVE, SVC, PendSV, IRQ0, SysTick, and MPU control tests also remained in that run. M4f control stopped on an MVE fault.

This is NVIC core testing with software pending. GPU peripheral GPIO connection, GPU IRQ acknowledgement, RTOS priority-4 preemption, and GPU work completion remain unverified. It did not connect new GPU MMIO handling or reboot original main.

## Proposed next implementation

Recommended sequence retains actual original main; a large renderer/backend implementation has not yet been selected:

1. Model GPU IRQ clear/reset and IRQ28 path connected to power state; stop GPU access on power failure.
2. Capture actual firmware command-list addresses, lengths, and memory accesses. Do not answer unknown commands as completed.
3. Define command-decoder/pixel-backend contracts and test a small source-confirmed command set first. Consider SDK for generating reference command fixtures.
4. Identify actual GPU framebuffer format and display boundary before connecting integrated screen.

Do not substitute an LVGL software demo or existing independent renderer for original main execution. This plan does not authorize installing a GPU driver on physical hardware or flashing new firmware.

## Evidence and reproduction

Private `simulator/gpu-initialization-research-01/` preserves repository trees, 16-file manifest, archive analysis, official HAL source, prior Renode path inventory, and source candidates. Initial per-member undefined references in archive analysis are preserved separately; final analysis compared archive-wide definitions. Download preflight observed a 1.79 MB file above 1 MB, then adjusted the limit to 2.5 MB for that research file. The full SDK was not downloaded.

```sh
python tools/analyze_gpu_initialization.py <private-inputs> \
  <gpu-response-main-comparison-report.json> <new-private-output>
```

`gpu-initialization-signature-03/report.json` contains static pattern results for three images. `gpu-irq28-core-smoke-01/report.json` contains separate synthetic core execution. No physical access, flash, OTA, MRAM changes, or external publication.

Independent review noted initial analysis checked only BL argument patterns; it was strengthened to inspect target NVIC address literals and write instructions. Initial signature-01 was preserved and signature-03 used as final static evidence. Renode commit was directly verified through commits API.
