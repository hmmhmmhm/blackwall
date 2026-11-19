# Connecting ADC Trigger and Conversion

Status: pinned HAL/header and Ambiq datasheet 1.1.0 research complete. Implementation begins at the conversion boundary at first trigger. Full boot, integrated display, physical ADC, and actual clock verification remain incomplete.

## Established connections

Pages 90–92 of the [Ambiq Apollo510 datasheet 1.1.0](https://contentportal.ambiq.com/documents/20123/2877485/Apollo510-SoC-Datasheet.pdf/6f7b4ae1-6630-d80c-1e17-ec7445b0509e?download=true&t=1780184793760) describe sequential scans of eight request slots, a 16-entry FIFO, and conversion/scan completion and FIFO-related IRQs. Figure 17 on page 90 was rendered and inspected. HFRC connects to the ADC digital controller, but this figure alone does not establish the exact internal repeating timer source Hz or first interval. Preserved PDF SHA and nine offset C compile checks are in private `adc-trigger-conversion-research-01/source-report.json`. PDFKit text extraction produced a CoreGraphics warning, but the 302-page marker and relevant sections 13.1/13.2/13.4 were checked and page 90 visually inspected.

The header says the timer restarts at zero after reaching TIMERMAX. CLKDIV is the number of divide-by-two operations; public HAL enums name codes 0/1/2/4 (code 4=divide 16). Actual source clock, reset, and first cycle edge are unknown. FIFO holds older data, count, and slot and pops on write. FIFOPR read-pops when CFG.DFIFORDEN is set. HAL can mask INTSTAT with INTEN and reads status after writing INTCLR. ADC IRQ number is 19. This is code/chip-document evidence, not verification of G2 IRQ/pin/sensor connections or actual measurements.

## First-trigger model

`--adc-trigger-source-hz HZ` is an explicit virtual source-clock assumption and depends on the ADC enable latch. It sets only bit 31 of a known disabled timer word and accepts only the limited ADCEN=1/RPTEN=1/RPTTRIGSEL=internal case. Source Hz must be 1..48000000 and produce an integer Hz after division. Only HAL-named divider codes 0/1/2/4 and TIMERMAX 1..1023 are supported. The report states the assumption that the first event is after TIMERMAX ticks. Even selecting 24 MHz as the reference frequency is not evidence that the actual G2 timer runs at that frequency.

A Renode virtual clock timer records trigger-consumption-required at the first event and requests machine pause. This diagnostic boundary stops because the first conversion of a repeating peripheral is not yet supported. It generates no sample, FIFO, completion bit, or ADC IRQ. Timing is not physical hardware verification, and CPU/timer synchronization and stop boundaries also have limits. Repeating the same start word does not restart the timer. Active reconfiguration, disable, and continued execution remain blocked. Prior timer configuration storage follows the existing option; without this model selection, TIMEREN 1 remains blocked.

## Complete ADC path to connect

Connect first trigger → sequential active-slot processing → explicit virtual channel digital input → averaging/precision → FIFO 16 and overflow → conversion/scan pending → INTEN mask/NVIC19 → guest ISR. Do not invent voltage, temperature, battery values, or analog error as actual measurements. Distinguish raw sample input from sample-correction code. DMA, window comparator, external trigger, and reset each need further evidence and execution results. This plan or timer success alone does not complete the ADC model, full main, or display goal.

trigger-consumption-required is a diagnostic state requiring a subsequent model. Whether the first timer edge is consumed as an actual scan or software trigger must first start it is unconfirmed. The event is not reported as having caused conversion.

## Load-failure diagnosis and correction

The first native run ended after a 45-second timeout and was not used as success evidence. A successful exit of the prior pinned baseline and a new source comparison narrowed the scope. Console monitor showed CS1503: a non-bus IPeripheral timer used bus-specific `GetSystemBus(this)`. The public `IMachine.SystemBus` property was confirmed by reflection and the code corrected. Compile diagnostics and two initial armed/event cases passed afterward. Runner and verifier use quit after console and script to expose errors in logs. However, a compile error that stops the startup chain can prevent reaching quit, leaving a wait until the 45-second timeout. This was confirmed in a negative check; fast error exit is not claimed verified. Missing required result records still cause failure.

The first include-only probe's Python marker was before machine creation and is not used as independent evidence of compile location. Machine-name quoting in the first API query was also wrong and corrected. Cause evidence is the actual console compile error and single-variable source comparison; auxiliary diagnostic failures are not replaced by success. Original failures, baseline, and corrected diagnostics are preserved privately.

Additional pre-pause observation reads machine state before the host test pauses it. It distinguishes a claim that the first event stopped execution from forced pause after the host window ended. Whether the exact timer edge is accepted as an actual G2 scan remains unverified.

## Headless console input boundary

A long main run ended with OutOfMemoryException in a console input worker repeatedly processing EOF. The memory limit was not raised. The first fix, retaining only the host pipe, had the same OOM because Docker closed container stdin. A separate bash read-timeout diagnostic confirmed immediate EOF without Docker `-i`, and maintained input wait with it. In console mode, `execute` retains an empty pipe writer and connects Docker `--interactive`. It sends no input bytes. The descriptor closes after owned container cleanup on success, failure, and timeout. After correction, the same 15-second main completed and left results. Failed main01/02, successful 03, pipe-only intermediate helper, and initial helper are all preserved privately.

Machine state before host pause alone does not establish the stop cause. MMIO strict abort can also stop the machine. If main timer event and unsupported access are both observed, report a mixed reason. This does not prove physical ordering of the two events or exact first-stop atomicity. Native armed/event controls without strict access separately confirm timer pause behavior.

## Final results

Private `adc-first-trigger-verification-01/final-verification.json` confirms corrected-backend native 23 (17 new/6 regression), main 7, and core/combined source snapshot agreement. Checks cover HAL-named dividers 1/2/4/16 and maximum count 1023, invalid starts, reconfiguration, routing, partial width, fractional frequency, and zero count. Native armed/repeat had machine paused=false before host pause; first-event cases were true. This control confirms the timer's pause request, not physical timing.

Under a 24 MHz assumption, stock 2.4, stock 2.3, and Faceclaw recorded both event 1 after TIMEREN request and blocked SWT `40038008`=37 write. PC is `57abc2` for stock 2.4 and `57c1ee` for the others. Under a 16 Hz assumption, stock 2.4 was blocked at the same SWT with event 0/armed. Main pre-host-pause state was also true on guard stop, so it is not used alone as cause evidence. Default unselected stops at TIMEREN request, stuck-off at timer configuration, and unknown info fixture at `42003300` read/word-copy PC 48.

All runs generated 0 ADC conversions, FIFO data, and ADC IRQs; full boot, integrated display, and real device remain unverified. Next is the software trigger requested by actual main, initial scan acceptance conditions, and explicit virtual channel input/FIFO/IRQ connection. Three CLI dependency/range errors were rejected before input and Docker. Deliberately invalid compile source logged the error and cleaned up after the 45-second timeout. This delayed error exit remains a tool improvement. Successful main03 is not confused with failed 01/02.
