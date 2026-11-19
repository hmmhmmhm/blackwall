# Prerequisites for Executing an ADC Software Scan

Status: source metadata, stock24 static-path investigation, and reproduction-tool verification complete. This work did not change the runtime model. Current main remains blocked at SWT 37; full boot, integrated display, and real device are unverified.

## New original material

[Ambiq's official Apollo_DFP 1.6.0](https://download.ambiq.com/packs/AmbiqMicro.Apollo_DFP.1.6.0.pack), found in the [Arm Keil device pack list](https://www.keil.arm.com/packs/apollo_dfp-ambiqmicro/versions/), is preserved outside Git. Its PDSC assigns SVD/apollo510.svd to AP510BFA-CBR (Apollo510 Blue) as well. The exact G2 part/revision has not been confirmed; this is a source-supported combination distinct from device measurement. Pack SHA is `4af5ead00786b6416dff699ee62433abd7b09d12768db8735f3962abeae503f2`.

SVD version 1.0 ADC base `40038000` and 30 registers were investigated. All 140 field masks matched the pinned HAL header, and all 30 offsets were checked against actual ADC_Type with C compile assertions. The pack header as a whole has a different SHA from the pinned header, so full SDK/all-peripheral compatibility is not claimed. The source-supported comparison scope is ADC.

The SVD specifies reset 0 for eight slots, CFG, timer, FIFO, and interrupt registers. This supplies a basis for a new virtual reset profile, but physical G2 power-off/on retention and initial values after stock boot remain unmeasured. Earlier decisions to leave values unknown are not retroactively changed. Existing runtime unknown-read blocking remains. SVD read-write labels alone are not grounds to implement FIFO, INTSTAT, and other side effects as scalar storage.

ARM example-template wording remains in the file, so it is not used uncritically as a device description. Only limited metadata supported by the official pack's device mapping and matches of 140 fields and 30 struct offsets against the pinned header is used. Redistribution permission for the entire original pack was not determined; raw material is preserved privately.

## Reproduction tool

`tools/analyze_adc_metadata.py` first checks SVD/header hashes, compares 30 direct ADC registers and 140 fields, then compiles 30 actual struct offsets with LLVM 21 on the current Mac. This source-layout check is not an ARM runtime execution test. JSON contains register/field/reset/enum numbers and is not an executable model. Other devices/headers are rejected before output directory creation. Two rejections were confirmed for Apollo510L SVD and another pack header. The first exploration script failed expecting bitWidth/bitOffset; after confirming the actual bitRange format it was handled strictly. This tool is for pinned ADC material, not a general SVD parser or automatic peripheral emulator.

```sh
python3 tools/analyze_adc_metadata.py \
  "$HOME/Library/Application Support/Blackwall/simulator/apollo-dfp-research-01/apollo510.svd" \
  "$HOME/Library/Application Support/Blackwall/simulator/upstream/hal-ambiq-61b293a/apollo510.h" \
  "$HOME/Library/Application Support/Blackwall/simulator/adc-metadata-validation-new"
```

Output must be a new path. Verification is preserved in private `adc-metadata-validation-01/report.json`; provenance, limits, and negative checks are in `adc-software-scan-research-01/source-report.json`.

## Static evidence for the actual firmware path

In stock24, LR at the runtime SWT stop is `4fb660`. The caller enables the timer, calls SWT, polls FIFO `40038038` COUNT, requests one sample at a time, and increments a count when the returned slot is 3 until it reaches three. It then calls candidate timer-disable and ADC-disable functions. See instructions/literals in private `stock24-call-path.json`. This is a binary-supported static path, not evidence that execution proceeded past SWT.

Current SL3CFG `7800301` specifies channel 3, 12-bit precision, 128-sample averaging, and tracking 32. The HAL sample macro shifts DATA right by six bits to obtain an integer sample. The signal actually connected to channel 3 and its voltage were not confirmed. The SVD RPTEN description specifies the first scan on the first trigger and subsequent scans at RPTTRIGSEL intervals. TRIGSEL=software and actual caller order support the interpretation that software starts the first scan, but do not verify timer-edge acceptance conditions in hardware.

## Scope for the next functional model

1. Explicitly select this SVD for a new reset profile and use reset 0 for all eight slots. Do not silently inject it into existing models.
2. Use an explicit virtual channel 3 raw code and virtual conversion-time assumption. Do not present it as actual voltage, temperature, or battery measurement.
3. Connect the first software scan and subsequent periodic scans, slot order, averaging/precision, and FIFO 16 peek/pop.
4. Connect INTEN/INTSTAT/INTCLR/NVIC19 and do not pass FIFO saturation or unsupported DMA/window behavior as success.
5. Check the three samples requested by the caller, timer stop, and RPTEN clear → ADCEN clear before identifying the next main boundary.

COUNT timing before/after FIFO pop, actual conversion latency, and clock coupling need further evidence or explicit virtual-profile assumptions. This investigation or passing the metadata tool alone does not complete ADC, boot, or display.
