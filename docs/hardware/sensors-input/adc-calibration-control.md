# ADC Automatic Calibration Control Storage Model

Status: analysis of public source and the clear operation in three mains is complete. The executable model is verified separately. Full boot, display, ADC calibration/conversion, and actual temperature remain incomplete or unverified.

Pinned MCUCTRL metadata defines ADCCAL `4002010c` bit 0 CALONPWRUP as RW, initially 1, and bit 1 ADCCALIBRATED as RO, initially 0. Reserved bits 31:2 are also RO. Header offset `10c` and both masks were checked by compilation. Metadata was checked against the pinned tree's blob SHA1. `adc-calibration-control-research-01/source-report.json` preserves provenance, hashes, three assertions, and the LDR → LSR1 → LSL1 → STR instructions in all three mains. This code clears only bit 0.

`--adc-calibration-control` is an explicit digital model providing initial word 1 and RW bit 0 only. Bit 1 remains 0 because the ADC engine is not implemented; the model does not generate completion. Storing 0/1 merely records the automatic calibration request state for the next power-up and does not execute calibration. Partial-width access, other registers, and writes to read-only/reserved bits cause a first stop. This diagnostic policy does not imply an exception on actual silicon. Existing read blocking remains when the option is not selected. The source-supported initial value is not interpreted as the actual G2's current state. The ADC information zero fixture and control register are selected separately and do not establish each other's validity.

## Virtual tests

Fourteen conditions in private `adc-calibration-control-native-01/report.json` passed. The 12 new conditions cover initial value, actual read-modify-write clear, re-enable and repeated clear, completion bit remaining 0, rejection of RO/reserved bit writes, and blocking partial reads/writes, adjacent addresses, and the unselected option. Two existing conditions for five ADC information words and GPIO output preservation also passed. This verifies storage of source control bits; it does not execute ADC calibration or verify completion IRQ or physical accuracy.

## Four main runs

Stock 2.3, 2.4, and CFW each read ADCCAL once and stored 0 once. Status was 0; actual calibration and conversion were not performed. The next request writes 0x2000 to PWRCTRL.DEVPWREN `40021004`. Compiling the pinned header confirmed this bit is PWRENADC. The request hit first-stop; it does not show that ADC power was enabled. Stock 2.4 without the option was blocked at the previous ADCCAL read.

Private `adc-calibration-control-verification-01/final-verification.json` compared source snapshots from native 14 and main 4 with current sources. Five ADC information reads and GPU powered-off state were also preserved. Next is modeling the ADC bit separately from other bits in DEVPWREN/STATUS shared with GPU. Do not overwrite existing GPU state or implicitly create ADC ready. Full boot, integrated display, and real-device verification remain incomplete.
