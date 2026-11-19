# Identifying STIMER Interrupt Registers

Work bw-0153. Original ARM read at `40008900` accesses STIMER STMINTEN. General TIMER (40008000) INTEN is at offset 60; STIMER is base 40008800 + offset 100. The initial TIMER-region assumption was corrected by distinguishing these blocks; it was not a layout mismatch between existing CMSIS and documentation.

Seven header, Timer/STIMER HAL, and register documentation files from pinned hal_ambiq commit `61b293a49db34030c545f99101f7ebf6a3050314` were preserved privately in `simulator/timer-source-research-01` and checked against Git tree blobs and SHA-256. Sources include [STIMER HAL](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/am_hal_stimer.c) and [register documentation](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/stimer_regs.html).

STMINTEN/STAT/CLR/SET are 40008900/904/908/90c respectively. Defined fields in each register comprise 13 bits: eight compare, one overflow, and four capture; the remainder are reserved. Documented initial 0 and set/clear semantics are distinct from an actual counter, capture, and IRQ delivery model. Structures were extracted from the header and offsetof compiled for ARM M55 target.

The three pinned bundles/raw mains match previous run inputs byte-for-byte. At stock 2.4 PC 4a2d9a and stock 2.3/Faceclaw PC 49d1d2, a four-byte read guard was confirmed with r1=40008900, r0=1. The candidate function reads an address from a literal and performs `ldr r2,[r1]; orrs r0,r2; str r0,[r1]`. Currently the first read is blocked, so completion of the enable write has not been observed. Its meaning matches public HAL `STIMER->STMINTEN |= ui32Interrupt`, but entire-function or SDK-version equivalence is not claimed.

Thirty-five checks in `tools/inspect_stimer_interrupt_contract.py` passed. Evidence: private `simulator/stimer-interrupt-contract-01/report.json`, layout.c/o, compiler.log, and inspector.py. No new guest execution, device access, or model change was included. Minor parenthesis syntax and search-location errors in investigation commands were corrected; failed searches were not used as source evidence.

Next, add explicit interrupt storage and verify source-supported enable/set/clear/status behavior. A state without counter, time, compare events, capture, and NVIC delivery is not described as a complete STIMER implementation. Full main loop, display, and physical verification remain incomplete; product progress remains 13/29 (44.8%).
