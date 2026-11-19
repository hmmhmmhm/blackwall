# ADC Calibration Information Zero-Fallback Test

Status: information addresses, ADC initialization source, and main call context analyzed. No actual calibration values are supplied. Existing ITCM 48 word-copy and Info1 metadata analysis from `renode-info1-fixtures.md` and `simulator-runner-status.md` is reused. New diagnostics add registers and a bounded SRAM stack.

## Established information

The pinned HAL `61b293a` MRAM Info1 header defines these five words, with base `42002000`:

| Address | Name |
| --- | --- |
| 42003300 | TEMP_CAL_ATE |
| 42003304 | TEMP_CAL_MEASURED |
| 42003308 | TEMP_CAL_ADC_OFFSET |
| 42003328 | ADC_GAIN_ERR |
| 4200332c | ADC_OFFSET_ERR |

These are ATE temperature, measured voltage at temperature-sensor calibration, and ADC offset voltage: device-specific manufacturing calibration values. Source ADC initialization uses the three as floats. If zero, it selects default constants and measured=false. Additional zero gain/offset disables ADC sample adjustment. A source comment also says this does not mean all calibration data is valid. An erased word is not the same fallback condition as zero and is not automatically supplied by this fixture.

The actual stock 2.4 context was r0=`42003300`, r1=`20076564`, r2=1, PC 48, LR `495f59`. The caller candidate corresponds to the public `am_hal_adc_initialize` flow reading one word each for these three and two additional ADC calibration values. It is not confused with the public power-info cache's three-word batch read. Candidate return addresses in the raw stack alone do not establish a complete recovered call stack. Public code translating Info1 helper logical OTP offset to MRAM offset was also confirmed.

## Test contract

`--adc-info-zero-fixture` requires explicit MRAM source and existing zero metadata. It supplies 0 for five additional aligned DWORD reads and records counts per word. The existing allowance for three zero-metadata words remains; all other information, OTP, partial-width accesses, and writes remain blocked. This is a source-fallback research input, not valid manufacturing calibration; valid_calibration/hardware_verified are false. CPU returns, PC, and instructions are not skipped. Actual ADC conversion, temperature, voltage, and calibration precision are neither modeled nor verified.

Five pinned source files were checked against Git blob/SHA and preserved in private `info-read-copy-research-01`. `context-and-source-report.json` records ten address assertions, preservation of existing guards/output, and diagnostic context.

## Limited verification results

Twelve unique native conditions, 13 native runs, and four main runs were preserved. The name `otp` in the first native report incorrectly labeled an out-of-domain `40021900` probe; the original was retained and the label corrected to outside-domain. Actual OTP TEMP_CAL_ATE=`42006900` was separately tested after checking the pinned header/blob. That test did not read a real device's OTP; it confirmed virtual guard blocking. The core source manifest retains existing recorded hashes; the additional OTP header is in a separate extension.

All three mains read each of five words once and were blocked on MCUCTRL.ADCCAL `4002010c` read. Offset `10c` was confirmed by compiling the pinned public header. The comparison without the option was blocked at the previous `42003300`. Reading virtual SRAM `20076564..73` in stock 2.4 confirmed float32 bits for three public ADC source default constants and measured=false. This is a calibration-reference fallback, not current temperature. ADC conversion, precision, and sample adjustment branches are unverified.

`--capture-sram-window ADDRESS:BYTES` reads at most four aligned virtual SRAM windows of 4..256 bytes each. Alongside register/stack diagnostics, it performs no guest writes or PC changes. Four CLI negatives for out-of-range, unaligned, oversized, and missing fixture prerequisite were rejected before file/Docker access. Final evidence is private `adc-info-zero-verification-01/final-verification.json` and `fallback-observation.json`. Full boot, integrated display, and real-device verification remain incomplete.
