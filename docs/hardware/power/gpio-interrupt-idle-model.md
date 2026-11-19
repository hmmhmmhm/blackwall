# GPIO Interrupt Initial Idle Model

Status: analysis of pinned public metadata, HAL, and three main accesses complete. Implementation is tested separately in virtual scenarios. Full boot, display, and actual GPIO/CPU IRQ verification remain incomplete.

Addresses and field diagrams for 56 registers—EN/STAT/CLR/SET across seven groups each for N0/N1—in [public GPIO documentation](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/gpio_regs.html) were compared with pinned C header offsets. Diagram values for all 32 bits are 0 in each register. This supports interpretation of documented initial values, not a read of actual G2 immediately after boot. Separate from PADKEY, HAL interrupt control reads/writes EN in a critical section. status_get combines enable mask and STAT, and clear writes a mask to CLR then reads final STAT. SET generates events and is unsupported.

The GitHub connection tool returned Transport closed, so pinned raw originals were downloaded directly and checked against pinned tree blob SHA1. Private `gpio-interrupt-research-01/source-report.json` records metadata/header hashes, 56 offset compilations, and field-diagram checks. Public summary is `gpio-interrupt-register-map.json`. Actual EN-read candidates and exact main hashes for three mains are separately preserved. This does not mean the entire calling function/ABI was recovered.

## Implementation boundary

`--gpio-interrupt-idle` is explicitly selected with GPIO config storage. Seven EN words per channel start at 0 and are stored/read; initial idle STAT returns 0. CLR writes record requested bits. Since the model has no path creating pending bits, it cannot test CLR actually clearing nonzero pending. It does not claim implementation of nonzero-pending W1C or actual IRQ handling.

SET writes, STAT writes, CLR/SET reads, partial widths, and other interrupt banks are blocked by guard. PADKEY lock is not tied to EN access. External pin state, edge, level, NVIC IRQ generation, re-pending, and wake are unimplemented. This is an explicit idle experiment, not a real-device guarantee that external input remains absent. Omitting the option retains the existing initial EN read block.

## Virtual tests

Eighteen conditions in private `gpio-interrupt-idle-native-01/report.json` passed. Fifteen new conditions include initial EN/STAT, enable write/read, channel separation, last group, idle clear requests/accumulation, rejecting STAT/SET writes and CLR/SET reads, partial widths, out-of-range, and unselected option. Three existing GPIO protection/unwritten-read and GPU-off transition conditions also passed. Idle clear tests verify only request recording and zero status, not nonzero-pending W1C or IRQ generation.

## Four main run results

Stock 2.3/2.4 and CFW each recorded eight EN reads, one write, eight STAT reads, and seven CLR writes. N0 group 0 EN=0x10, the other 13 EN words are 0, and all CLR requested bits are 0. This is not evidence that actual nonzero pending was removed. Execution then blocked attempting 0x80 write to 0x40010458. Compiling the pinned header confirmed this is GPIO.WTC0 offset 458; output latch/pad behavior is not yet implemented. Stock 2.4 without the option blocked at previous EN 0x40010530 read.

Private `gpio-interrupt-idle-verification-01/final-verification.json` compares native 18/core 18 and main 4/combined source 4 against current versions. Missing required config option was also rejected before input/Docker. Full boot, later GPU submission, integrated display, and real-device verification remain incomplete.
