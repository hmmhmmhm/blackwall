# TON Power-Control Configuration Storage

Status: optional virtual model preserving configuration values written by actual firmware. Counter, clock, comparator, and voltage behavior are not implemented.

## Source and actual code

The [pinned PWRCTRL documentation](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/pwrctrl_regs.html) and [CMSIS definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/CMSIS/AmbiqMicro/Include/apollo510.h) were compared. Addresses and public reset value 0 were confirmed, but current actual G2 values are unknown. These do not substitute for actual calibration data or measured initial state.

Stock 2.4 function 0x5c22fe clears TONCNTRCTRL CLKDIV and sets FCNT to 1000. It then configures five threshold/hysteresis registers and clears LPMODESWOVR and ENABLELPOVR. The two bits control LP override and are not interpreted as the entire counter's enable bit. The public HAL header also [defines](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_sysctrl_ton_config.h) the relationship between TON and CPU/GPU power state. With no G2 symbols, identical function name or version to public HAL is not asserted.

## Allowed scope

`--ton-configuration-storage` is explicitly selected with the power model. All initial values are 0; only these values are stored through aligned four-byte accesses:

| Address | Name | Allowed values |
| --- | --- | --- |
| 0x400211a0 | TONCNTRCTRL | 0, 0x03e80000 |
| 0x400211a4 | LPOVRTHRESHVDDS | 0, 800 |
| 0x400211a8 | LPOVRHYSTCNT | 0 |
| 0x400211ac | LPOVRTHRESHVDDF | 0, 450 |
| 0x400211b4 | LPOVRTHRESHVDDC | 0, 600 |
| 0x400211bc | LPOVRTHRESHVDDCLV | 0, 250 |

Setting LP override bits, other divisors/thresholds, status-register reads, and partial widths stop. Stored FCNT is not converted to actual time or voltage waveform. Reports state `counter_clock_comparator_and_voltage_effects=not-modeled`, `lp_override_enable=unsupported`, and `hardware_verified=false`.

## Execution results

`startup-zero-info1-rev-23-ton-configuration-hypothesis` ran against pinned bundles for stock 2.3.0.24, 2.4.0.24, and Faceclaw 38. All three recorded four TONCNTRCTRL reads/writes each and one read/write each for the other five registers. Final values match the settings above.

All three then stopped as `unsupported-latch-access` on a 0x40008858 write. PC is 0x44df6c for stock 2.3/Faceclaw and 0x44e85c for stock 2.4. This address shares an MMIO page with the existing 0x4000885c shadow hypothesis but is a separate register. Static observation only showed subsequent code attempting to write 0 and 0x5af00000; meaning was not yet established. The write was not passed by assuming timer or reset behavior.

Subsequent investigation identified this address as HAL internal clock recovery state HALSTATES and 0x5af0 as the public HAL signature. Follow the later [HAL state model](../cpu-memory/hal-state-model.md) results.

Original source hashes, three image code contexts, and execution JSON are preserved outside Git in `Blackwall/simulator/ton-configuration-01/`. Seventy-eight runner tests and three scenario tests passed, checking normal configuration readback and rejection of override bits, unobserved values, status reads, partial widths, and missing model. Full boot, display transport, actual installation, and recovery verification remain incomplete.
