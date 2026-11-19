# ADC Enable Bit Latch

Status: pinned header/HAL analysis and digital latch native 22/main 6 verification are complete. Full boot and integrated display remain incomplete.

Public `am_hal_adc_enable` sets CFG.ADCEN bit 0 and changes software bEnable to true. It does not read STAT, wait for conversion, or return a sample. Disable first clears RPTEN and ADCEN, changes some clocks, and releases HFRC. This entire path is not automatically included in the one-bit enable model. All three actual mains requested a change from CFG `2171014` to `2171015`. Pinned image SHA and instruction candidates are in private `adc-enable-research-01/main-enable-candidates.json`; HAL analysis is in the same folder's source report.

## Model boundary

`--adc-enable-latch` requires both existing ADC config bank and timer config storage options. Virtual ADC power must be on, guest-written CFG ADCEN must be 0, and a known disabled timer configuration must exist. It accepts only a request changing bit 0 to 1 while retaining the rest of CFG, recording one enable request. Repeated writes of the same enable word are allowed without increasing the enable transition count. Writes changing CFG/slots, RPTEN clear/disable, and restart are not yet supported. Timer configuration rewrites after enable are also blocked.

These prerequisites are the conservative scope of a limited model, not the full order required by actual HAL or a silicon fault policy. CFG ADCEN readback is distinct from actual analog ADC ready/clock/calibration/scan. Report field adc_enabled is bit 0 of known CFG, not physical readiness; an unknown initial value is null. STAT/SWT/FIFO/IRQ/DMA, timer start bit, and conversion events remain strictly blocked. No device was accessed.

## Limited native verification

Sixteen new and six regression cases in private `adc-enable-native-01/report.json` passed. They check bit 0 readback, repeated identical enable word, unwritten timer/CFG, mixed/reserved writes, disable/RPTEN clear, slot/timer changes, timer start, STAT/SWT, partial width, and unselected feature. Existing bank/slot/timer/power regressions are included. The checks cover register latch and strict stops, not actual readiness, conversion, or IRQ execution. Actual main results are recorded separately.

## Actual main results

Private `adc-enable-verification-01/final-verification.json` confirms native 22 and main 6 match the current source snapshot. All three active inputs, stock 2.4, stock 2.3, and Faceclaw, showed one enable request, CFG `2171015`, and preserved slot 3 configuration. CFG had 3 writes/2 reads; execution then stopped on a request for `8004001e` (TIMEREN 1) at INTTRIGTIMER `40038040`. The previous disabled timer `4001e` remains at 1 write/1 read. PC is `57a78c` for stock 2.4 and `57bdb8` for the others. This is not evidence of timer, scan, sensor value, or IRQ execution. This latch has no physical ready behavior.

Without the option, the ADCEN request is blocked. Stuck-off is blocked at the earlier timer configuration write and CFG is unknown. An additional run excluding the ADC calibration info fixture stopped at `42003300` read/guest word-copy helper PC 48, confirming initial CFG bit and enable request state as unknown/0. PC 48 is not classified as a ROM error or full boot. CLI dependencies are rejected before input and Docker execution. Actual glasses were not accessed.
