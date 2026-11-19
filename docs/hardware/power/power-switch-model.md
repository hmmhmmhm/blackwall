# Power Rail Static-Select Configuration Storage

Status: optional virtual model storing observed PWRSW control values. Actual rail switching, voltage, stabilization, and readiness are not implemented.

The [pinned MCUCTRL definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/mcuctrl_regs.html) and CMSIS header were compared. 0x4002037c is PWRSW0, and 0x40020380 is PWRSW1. Virtual initial values calculated from public reset bits are 0x80 and 0 respectively, not actual device state.

After 0x49549c, stock 2.4 sets PWRSW0 bit 30 and then PWRSW1 bits 16 and 12 in order. These are rail static-select settings. A power management function is called afterward, so this is not treated as equivalent to cache reads.

`--power-switch-storage` is selected with the existing MCUCTRL model and stores only these values:

| Register | Virtual initial value | Allowed values |
| --- | --- | --- |
| PWRSW0 | 0x80 | 0x80, 0x40000080 |
| PWRSW1 | 0 | 0, 0x10000, 0x11000 |

Only aligned four-byte accesses are allowed; unobserved override values and partial-width accesses stop. This option does not perform actual register changes or voltage switching. It generates neither voltage nor ready values and records `rail_switching_voltage_and_readiness=not-modeled` and `hardware_verified=false` in reports. The two addresses were not added to the read-only trim reset catalog; the write model is separate.

`startup-zero-info1-rev-23-power-switch-hypothesis` was run for each of three images. After confirming PWRSW0 final value 0x40000080 with one write and PWRSW1 final value 0x11000 with two writes, execution stopped at a 0x400211a0 read inside the power management function. PC is 0x5bad58 for 2.3/Faceclaw and 0x5c2300 for 2.4. Results are preserved outside Git in `Blackwall/simulator/power-switch-storage-01/`.

Seventy-six runner tests and three scenario tests passed, including rejection of unobserved override writes and partial reads. Full boot, display transport, actual installation, and recovery verification remain incomplete.
