# Limited Storage of CLKGEN Control Values

Status: offline model reproducing observed initialization accesses in pinned main binaries. Oscillators, actual clock/frequency, stabilization, and ready state are not implemented.

## Source and actual code

The previous next boundary was 0x40004044. After 0x4952d4, stock 2.4 reads the value, ORs 0xf80000 and 0x3bfc0, clears 0x4000, and stores it. With virtual initial value 0, the result is 0xfbbfc0. It then writes 0 to 0x40004120.

The [pinned CMSIS header](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/CMSIS/AmbiqMicro/Include/apollo510.h) was fetched from the original commit and checked against its Git blob SHA. The actual header is 10,449,123 bytes, blob `a63686ff4feb43e97a33fcc0787e76b748a783e6`, SHA256 `b6ca35dc828ef95825c0a22f06e6ca5ed558a6542dc74310515fdc350051a797`. The original is outside Git at `Blackwall/simulator/upstream/hal-ambiq-61b293a/apollo510.h`. The expected CLKGEN register HTML path was absent in that commit, so the header was directly inspected.

Compiling the header's CLKGEN structure with clang confirmed MISC offset=0x44, CLKCTRL offset=0x120, structure size=0x124. Source, executable, and `layout-verification.json` are preserved outside Git in `Blackwall/simulator/clock-gate-storage-01/`. This is a host compiler offset check, not actual chip verification.

## Optional model

Select `ClockGateStorage` in `tools/simulator_clocks.py` with `--clock-gate-storage`. Both registers use explicit virtual initial value 0, not a confirmed actual-device initial value or public-definition reset value.

| Address | Register | Allowed stored values |
| --- | --- | --- |
| 0x40004044 | MISC | 0, 0xfbbfc0 |
| 0x40004120 | CLKCTRL | 0 |

Only aligned four-byte accesses are allowed. Other registers, values, and partial-width accesses stop as `unsupported-clock-access`. Other values enabling HFRC96 trunk gate bit or GFX clock enable are also rejected. No clock-ready or frequency value is generated. Reports state `frequency_and_readiness=not-modeled` and `hardware_verified=false`. Storing control values does not verify actual gate, GPU, or display behavior.

## Actual input execution

`startup-zero-info1-rev-23-clock-gates-hypothesis` adds this option to the existing synthetic initial state. Unimplemented boundaries of other scenarios remain. Three CLI runs for stock 2.3/2.4 and Faceclaw38 confirmed:

- One MISC read and write each, final value 0xfbbfc0.
- One CLKCTRL write, final value 0.
- Stop at the next 0x40020448 MCUCTRL read.
- PC: 0x48940c for 2.3/Faceclaw, 0x4952f4 for 2.4.

All three reports are in private `clock-gate-storage-01/`. Sixty-eight runner tests and three scenario tests passed. Full boot, RTOS, display transport, actual web installation, and recovery verification remain incomplete.
