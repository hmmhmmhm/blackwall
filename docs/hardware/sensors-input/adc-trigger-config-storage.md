# ADC Internal Trigger Configuration Storage

Status: public header/HAL analysis and native/main verification of the limited configuration storage model complete. Full boot, display, timer, ADC conversion, and IRQ remain incomplete or unverified.

INTTRIGTIMER `40038040` has TIMEREN bit 31, CLKDIV bits 18:16, and TIMERMAX bits 9:0. Observed value `4001e` means timer disabled, divider code 4, count 30. Public HAL configure_irtt also stores configuration with TIMEREN=0; its separate enable function checks ADC_CFG.ADCEN and writes bit 31. Only clock divider codes were confirmed; actual clock frequency, time, and sample rate were not measured.

No general `adc_regs.html` was found in the pinned tree, only `audadc_regs.html`. AUDADC is not used as evidence for general ADC reset values. The source report records the confirmed metadata path and unconfirmed ADC reset value (null). The initial search for the general ADC documentation path failed and AUDADC material was not substituted. Four offsets/masks were compiled in C. See private `adc-internal-trigger-research-01/source-report.json`.

## Model contract

`--adc-trigger-config-storage` is explicitly selected with ADC power response. Only when virtual ADC phase=on does it allow DWORD writes with TIMEREN=0 and defined field mask `703ff`. Readback is allowed only after a guest write; unknown unwritten initial values are blocked. TIMEREN=1, reserved bits, partial widths, and adjacent registers are blocked. No timer, conversion, or IRQ is generated.

Access in requested/stuck-off/off power states first-stops and records power_blocks. This conservative diagnostic policy does not verify actual silicon bus-fault behavior. A bit response saying ADC state is ready does not mean physical readiness or clock stabilization. The prior attempt to access the timer under stuck-off is not hidden, nor is a value stored to make it look successful.

## Implementation boundary

The ADC address belongs to the board's high guard, split by the watchdog, but one low guard owns power state and configuration storage. The high guard uses the same state through an existing owner reference. The guards do not create different power states or configuration values. The internal placeholder for the first value is not exposed to guest reads; reports leave unset values null.

## Limited model verification

In `adc-trigger-native-01/report.json`, 16 new cases and three ADC power regressions passed. They cover configuration write/read, maximum fields, zero, rewrite, preserving the previous value after an invalid rewrite, blocking initial unknown reads, start/reserved bits, partial widths, adjacent addresses, power off/requested/stuck-off, and the default unselected boundary. Actual main execution through the high guard is recorded separately; this test alone does not establish boot.

## Actual main results

Private `adc-trigger-verification-01/final-verification.json` confirms native 19 and main 5 runs and source snapshot agreement. Stock 2.4, stock 2.3, and Faceclaw active runs each stored timer configuration `4001e` once, then stopped attempting to write `2171014` to ADC.CFG `40038000`. PC is `57a6a4` for stock 2.4 and `57bcd0` for the others. Stock 2.4 stuck-off stopped at timer configuration with power_blocks=1 and configured=false/value=null, rather than appearing to pass the failure condition. The unselected option retains the existing timer write stop.

CLI dependencies were confirmed rejected before input files and Docker execution. Main configuration storage resulted from the split high guard routing through the low owner, distinct from merely passing a separate native fixture. Timer timing, ADC conversion, full boot, integrated display, and real-device verification remain absent.
