# Disabled ADC Configuration Bank

Status: public header/HAL analysis and limited configuration bank native 27/main 6 verification complete. Full boot and integrated display remain incomplete.

Before adding the model, three actual main inputs stopped at ADC.CFG `40038000`=`2171014`. Public header interpretation is CLKSEL 2, RPTTRIGSEL 1, TRIGPOL 0, TRIGSEL 7, DFIFORDEN 1, CKMODE 1, LPMODE 0, RPTEN 1, ADCEN 0. HFRC 24 MHz is a HAL enum name, not verification of actual frequency or clock stabilization. The actual main write instruction is `STR r5,[r0]` at stock 2.4 PC `57a6a4` and stock 2.3/Faceclaw PC `57bcd0`.

Private `adc-disabled-config-research-01/source-report.json` records pinned header SHA and 66 C compile checks: nine CFG/8-slot addresses and 57 field masks. Nine check actual struct offsets; 57 compare source macro literals to the same extracted numbers and are self-consistency checks. The latter do not verify bitfield layout or silicon. Full CFG mask `71f101d` excluding ADCEN is `71f101c`; slot mask is `7ff0f03`. SL0..7CFG are spaced four bytes apart from offsets `0c` through `28`. Public HAL configure writes with ADCEN clear, and the header says not to change configuration while ADCEN=1. Slot HAL checks tracking 32..63 and the public channel enum is 0..11.

## Limited model contract

`--adc-disabled-config-storage` requires ADC power response. The high guard references the low owner's single bank. Access is allowed only when virtual power is on. CFG permits ADCEN=0, defined bits only, HAL configure clock code 2, and public trigger codes 0..4/7. Slot writes are allowed only after the guest writes disabled CFG. The eight slots accept only defined bits, tracking 32..63, and channel 0..11. Slot enable/window enable are stored only; measurement and comparison do not execute while the whole ADC is disabled. This is conservative model scope, not silicon bus-error policy.

Initial values are unknown. Only registers written by the guest can be read. Invalid CFG/slot writes preserve the previous value and first-stop. ADCEN 1, reserved bits, partial widths, STAT/SWT/FIFO/IRQ/DMA, and adjacent addresses are strictly blocked. No timer start, conversion result, sensor value, or IRQ is generated. Timer storage is an existing separate option; this bank does not enable it automatically.

Report field adc_enabled is null before a guest CFG write and false only after disabled CFG is written. Selecting the configuration model alone is not reported as confirming initial ADC enable state. This was found and corrected in independent review.

## Execution evidence

Private `adc-config-verification-01/final-verification.json` confirms 23 new and 4 regression native cases, six mains, and byte agreement of 27 current core prefixes and six main combined sources. Scope is register storage and blocking. Checks cover initial unknown reads, CFG rewrites, invalid enable/reserved bits/clock/trigger, slot writes before CFG, unwritten slot reads, slot tracking/channel/reserved bits, round trips for all eight slots, partial width/status/software trigger/slot range, power off/requested/stuck, and option not selected. Existing regressions under the same power/timer assumptions are included.

Actual stock 2.4, stock 2.3, and Faceclaw mains all stored CFG `2171014` and SL3CFG (offset `18`) `7800301`: slot 3, averaging code 7, tracking 32, precision 0, channel 3, slot enable 1, window compare 0. They stopped after one CFG read when attempting to write `2171015` (ADCEN 1). Stored CFG remained `2171014`. PC is `57a946` for stock 2.4 and `57bf72` for the others. This is not interpreted as ADC start, scan, sensor value, or interrupt execution.

Stuck-off stops at the earlier timer write boundary with an empty bank and enable null. Without the new option, the existing CFG `2171014` write stop remains. An additional run without the timer option also reported adc_enabled null with an empty bank, confirming it does not assume the initial state is false. The CLI checks dependencies before input and Docker.

Full boot, app loop, display path, lens output, and real device remain unverified.
