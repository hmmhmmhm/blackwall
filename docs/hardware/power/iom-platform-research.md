# IOM2 Research and Reuse Boundary

Work bw-0114. Original main still stops at the IOM2 power request. Standalone model tests below do not mean original-main IOM initialization, transfer, boot, or display succeeded. Actual glasses were not accessed.

## Confirmed original path

Current stock 2.4 call/stack and limited SRAM snapshot were compared. Board registration table is 20002a4c, index 2 handle 2003f9d8, configuration 20002a0c. The first static lookup failed by assuming the table pointer was in ROM. Original main was then rerun with the existing bounded capture option to read SRAM.

Configuration offsets mode 0, clock 4, SPI mode 8, NB pointer 12, and NB length 16 were confirmed from configure-callee loads/branches. Values are mode 1 (I2C), requested 400000 Hz, NB pointer 0/length 0. IOM4 configuration in the same snapshot is 1 MHz, NB pointer 203366e0, length 800 (hex). These express guest configuration intent, not actual bus-clock measurement or completed configuration writes. Connected peers are unknown.

`am_hal_iom_config_t` in the [pinned public HAL](https://github.com/zephyrproject-rtos/hal_ambiq/tree/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu) orders clock/NB pointer/NB length/mode, differing from the actual firmware ABI. Its layout is not applied directly to G2 or replaced by a function bridge. Register-level execution remains and is checked through actual callee and MMIO. The complete stock 2.3/CFW config ABI is not established from this snapshot.

## Existing engine

[Pinned Renode IOMaster source](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/SPI/AmbiqApollo4_IOMaster.cs) implements SPI/I2C FIFO polling, transfer, and some IRQs. Source is MIT and is a candidate for reusing the pinned runtime instead of duplicating it. Byte identity of source and runtime assembly was not established.

In the pinned runtime, a synthetic I2C peer 48 (hex) was used to observe four-byte transmission, six-byte reception, order, transfer termination, and IRQ clear. This did not identify an actual G2 peer or reproduce sensor values. DMA and command queue are unexecuted tag placeholders in source, not actual execution engines. Enable-write readback was also 0. The core treats missing peer as IllegalCommand; this is not assumed equivalent to physical I2C NACK.

## Apollo510 differences

Thirty-six offsets and 154 field masks from official DFP IOM0 register definitions were compared with the pinned header, and 36 C offsets compiled with LLVM 21 on the current Mac. This verifies numeric definitions and C register layout, not physical behavior or the firmware config ABI above.

- IOM2 base 40052000, IRQ 8, power mask 8. IOM1–7 inherit IOM0 layout.
- Apollo510 CLKCFG has FSEL[11:8], DIV3 bit 12, DIVEN bit 13. Apollo4 model uses 3-bit FSEL and bits 11/12 respectively.
- The model exposes I2S offsets 300/304/308 and upper SUBMODCTRL type bits absent on Apollo510.
- Runtime FIFOCTRL.FIFORSTN readback was opposite for assert/release, matching the source value provider.
- Model idle state and FIFO remainder differ from SVD reset numbers and are not claimed as physical reset values.

It is therefore not connected unchanged. Clock storage and FIFOCTRL readback must be owned at the Apollo510 boundary, with extra bits/offsets, unsupported widths, DMA/CQ enable, and unsupported transactions strictly blocked. Actual timing, DMA, CQ, complete SPI functionality, and peer behavior remain unverified.

## Connection alternatives and recommendation

Direct mapping was not adopted because it silently accepts unsupported fields. Keeping an internal core as an unregistered object, as with UART, also caused a peer-parent registration error in a native probe. The recommended candidate is a derived IOM model registered on the bus that owns a strict interface and inherits the base polling engine and child registration. Only the selected IOM range should be separated from the guard; remaining space and unknown power-bank bits must remain blocked.

A separate 11-condition prototype checked clock/FIFO/type correction, byte/word/quad rejection, DMA/CQ enable and extra I2S rejection, Reset interface dispatch, and inherited I2C peer transfer. The prototype wraps only some offsets and cannot serve as production strict IOM. Power integration, full masks/permissions, IRQ8 wiring, peer address/model, and original main execution need subsequent verification. In particular IOM4 may require NB/CQ and is not marked supported by the existing engine alone.

## Evidence and follow-up

Private iom-research-01 download/renode-source/register-map/call-path-report-v2 and sensor-string-candidates were preserved. Stock strings for OPT3007/ICM45608 driver paths are candidate evidence that code is present, not confirmation of IOM2 connection or actual parts.

Actual checks/failures are preserved in private iom-metadata-validation-01, iom-runtime-probe-01, iom-runtime-unmapped-probe-01, iom-interface-probe-01, and iom-call-path-main-stock24-01/02. Follow-up is to compare initialization progress/differences across three original mains after connecting mapped strict adapter and power domain, and connect an explicit device model when a peer is identified. Do not modify ROM/main/PC to pass.

Independent review's instruction not to determine actual ABI NB length units from the name was incorporated. call-path-report-v2 uses nb_length_field_value and units unverified, without changing original snapshot values. Two metadata original-hash mismatch conditions were also confirmed rejected. Review was same GPT-6-family fallback, with no separate transcript archive. No further significant findings were reported.
