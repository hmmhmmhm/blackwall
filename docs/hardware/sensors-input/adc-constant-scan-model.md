# ADC Scan and FIFO Model with Explicit Input

Status: virtual functional profile implemented. Full boot, display, and actual ADC measurement remain incomplete.

`--adc-constant-channel3 0..4095` requires the ADC enable latch and an explicit trigger source Hz. This profile selects CFG/8-slot reset 0 from the pinned SVD. Existing profiles retain their unknown initial-value policy. Virtual input is a constant 12-bit raw code on channel 3. Averaging the same input produces the same value and 0 fractional bits. Only 12-bit precision 0/1 is supported; 10/8-bit, other channels, and window comparator are blocked. Conversion delay is assumed 0 and FIFOPR.COUNT is assumed to be the count remaining after pop. No actual voltage, noise, or timing accuracy is claimed.

SWT 37 performs the first scan, and subsequent timer events perform additional scans. Events before the first software trigger do not create scans. All slots and capacity are checked before applying results to FIFO in slot order; exceeding 16 entries stops without overwriting. FIFO supports peek/write-pop; FIFOPR read-pops when DFIFORDEN is set. Empty destructive reads are blocked. Pending CNVCMP/SCNCMP, 75%/full bits, and polled clear are modeled. INTEN permits only 0; actual IRQ/NVIC connection and DMA are unsupported.

After timer disable, RPTEN clear → ADCEN clear is allowed. Timer/ADC restart and power-off response are not yet supported. The timer report word is the last start request; current INTTRIGTIMER value follows adc_trigger_config.value. Primed records receipt of the first SW trigger; current ADC operation is determined from CFG.ADCEN and timer phase.

Report adc_constant_scan distinguishes functional_scan_implemented=true from analog_conversion_implemented=false. adc_internal_trigger.adc_conversions counts virtual post-average slot results, not individual SAR conversions. conversion=false in adc_disabled_config denotes the scope of the configuration storage component.

## Verification scope

`tools/verify_adc_constant_scan.py` checks C# model FIFO behavior without firmware. It has 39 assertions including 16 fill steps, so they are not counted as 39 independent scenarios. It checks 0/2048/4095 input, peek/pop, empty read, full prevention, pending clear, unsupported IRQ, non-destructive read, slot order, and atomic rejection of an invalid subsequent slot.

Actual ARM main comparison, source snapshots, and guest memory values are recorded separately in private `adc-constant-verification-01`. Success of this model does not prove actual hardware scan, recovery path, or full main boot.

## Actual main results

Private `adc-constant-verification-01/final-verification.json` confirms 39 unit assertions, three existing native regressions, main 6, and source snapshot agreement. With source SVD reset/constant profile selected, stock 2.4, stock 2.3, Faceclaw, and stock 2.4 with raw 0/4095 showed scan 3/sample 3/pop 3, FIFO empty, timer stopped, INTTRIGTIMER `4001e`, and CFG `2171010` (RPTEN 0/ADCEN 0). The subsequent DEVPWREN `40021004`=0 request was blocked. ADC power response remained on; safe power-off is not claimed. PC is `494f3e` for stock 2.4 and `489056` for stock 2.3/Faceclaw.

Words `2007fa90/94` in the stock 2.4 snapshot are sample/slot 3 respectively. For raw 0, 2048, and 4095 inputs, the same integer values and slot 3 remained, confirming the actual ARM sample-read path received virtual data. This memory was read within the existing bounded stack observation scope; guest memory was not overwritten. Virtual values are not interpreted as voltage/battery measurements.

Main without the new profile remains at the existing SWT 37 boundary. Invalid CLI code and three clock dependencies were rejected before input and Docker. After independent review, the initial unit's invalid-slot position moved to slot 5 to check failure after valid slot 3. Final main 6 was rerun after clarifying report wording; earlier main01/02 were not overwritten. Full boot, integrated display, and real-device recovery remain unverified; next is the source-supported virtual ADC power-off transition.
