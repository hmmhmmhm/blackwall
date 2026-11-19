# Audio ADC Delay Configuration Storage

Status: a virtual model reproducing only observed MCUCTRL initialization accesses in the pinned main. Actual ADC power-up, conversion, sampling, and time delay are not implemented.

According to the [pinned MCUCTRL definition](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/mcuctrl_regs.html), 0x40020448 is AUDADCPWRDLY. Bits 15:8 are AUDADCPWR1, bits 7:0 are AUDADCPWR0, and the upper 16 bits are reserved. The documented reset bits are 0x200. This is used as a virtual fixture, not as an actual user's initial state.

Stock 2.4 after 0x4952f4 reads the value and writes 4 into bits 15:8. `--adc-power-delay-storage` supports only aligned four-byte storage and readback of 0x200 and 0x400. It requires the existing MCUCTRL model and stops on other values or partial-width accesses. It does not convert delay units to actual time or create ADC clock state. The report retains `adc_power_conversion_and_timing=not-modeled` and `hardware_verified=false`.

`startup-zero-info1-rev-23-adc-delay-hypothesis` was run for stock 2.3, 2.4, and Faceclaw38. Each recorded one register read and write and final value 0x400, then stopped on the next read at 0x4002036c. The PCs are 0x489424 for 2.3/Faceclaw and 0x49530c for 2.4. Results are preserved outside Git in `Blackwall/simulator/adc-power-delay-01/`. Seventy runner tests and three scenario tests passed.

This is a limited execution of an initialization path using synthetic Info1, revision, and power state. It does not establish a working device's ADC or compatibility with full boot, display, or actual installation/recovery. The next register's calibration field meaning and uses of the read value require separate analysis.
