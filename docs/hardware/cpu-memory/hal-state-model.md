# HAL Clock-Recovery State Storage

Status: an optional model preserving only the HALSTATES initialization value and signature. Actual clock and mux recovery are not implemented.

## Confirmed meaning

The next stop address in the TON test, `0x40008858`, is not reset status. The [pinned STIMER documentation](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/stimer_regs.html) defines it as HALSTATES for internal HAL use; all public reset field values are 0. In the [CMSIS header](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/CMSIS/AmbiqMicro/Include/apollo510.h), the upper 16 bits are SIGNATURE and the lower seven are clock-recovery state and reference selection.

The [internal HAL header](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_sysctrl_clk_mux_reset.h) maps HALSTATE to STIMER->HALSTATES and defines signature `0x5AF0`. At the end of the [low-power initialization function](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_sysctrl.c), the word is cleared to 0 and then the signature is inserted. Initialized low state bits do not mean the clock is ready; the actual recovery path separately manipulates clocks and peripherals.

Stock 2.4 at `0x44e858..0x44e868` writes 0 to the same address, reads it, inserts `0x5af0` into the upper halfword, and writes it again. Stock 2.3/Faceclaw have the same form starting at `0x44df68`. This is correspondence between public HAL and binary, not physical device verification. Do not assume all G2 code matches this public HAL revision.

## Model boundary

Select `--hal-state-storage` only with the existing STIMER page adapter and explicit `--reset-latch` input. Its stored value and counts are separate from the neighboring virtual latch at `0x4000885c`. That latch's reset-status meaning remains a hypothesis and differs from HALSTATES' confirmed definition.

Only aligned four-byte reads/writes at `0x40008858` are supported. Virtual initial value is public reset value 0; allowed writes are only 0 and `0x5af00000`. Other signatures, low clock flags, partial widths, and adjacent registers stop execution. Reports retain `clock_mux_recovery=not-modeled` and `hardware_verified=false`. This does not make actual clock mux reset or clock readiness succeed.

## Execution and tests

Executed `startup-zero-info1-rev-23-hal-state-hypothesis` once each on pinned stock 2.3.0.24, 2.4.0.24, and Faceclaw 38 bundles. Each recorded one read, two writes, final value `0x5af00000`, then stopped at the `0x400211c8` read. Reason was `unsupported-power-access`; PCs were 2.3/Faceclaw `0x489606`, 2.4 `0x4954ee`.

Source commit/hash and execution JSON were preserved outside Git in `Blackwall/simulator/hal-state-storage-01/`. New public source Git blob SHA-1 was compared against the pinned tree. Passed 80 runner and three scenario tests, covering initial value and normal signature readback, separation from the latch, and rejection of wrong signature, clock flags, partial widths, and missing model. Full boot, display transport, and actual installation/recovery remain incomplete.
