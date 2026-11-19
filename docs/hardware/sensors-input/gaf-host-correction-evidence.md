# Applicability of GAF Host Correction Source

bw459. New official sources were investigated for the [existing dependency](gaf-render-scheduler-dependency.md) in which normal GAF blocks natural rendering. **Some numerical calculation code was found, but no execution evidence sufficient to complete normal GAF requests 2/4 was obtained.** No model, ARM execution, or physical device was changed. Overall progress remains 10/16=62.5%.

## Newly identified material

The official TDK [ICM45687 repository](https://github.com/tdk-invn-oss/motion.arduino.ICM45687/tree/dffaee833d41b1f786c7a19c4f01f4d7a2dd1e98) was pinned to commit `dffaee833d41b1f786c7a19c4f01f4d7a2dd1e98`, tree `ffd7d46da639c9eba280efa7824e577e7bcbe997`. The recursive tree was confirmed truncated=false. Thirteen edmp/gaf paths under src/imu were compared with the existing pinned ICM45608 tree, and all had different blobs. This is a count of paths compared under the filter, not a measure of functional improvement or compatibility.

Four files were read directly and checked against Git blob/SHA256: `inv_imu_edmp.c`, `inv_imu_edmp_gaf_patches_defs.h`, `edmp_prgm_ram_gaf_patch.h`, and `LICENSE`. This is not evidence that the whole repository was read or that all public execution code can be ruled out. ICM45687 is a different part from the G2's ICM45608.

## What the numerical code explains

In the [host driver](https://github.com/tdk-invn-oss/motion.arduino.ICM45687/blob/dffaee833d41b1f786c7a19c4f01f4d7a2dd1e98/src/imu/inv_imu_edmp.c#L501), `fix_clock_variation_negative` uses fixed-point arithmetic with int64 multiplication and a 30-bit shift to write the gyro time interval and some derived values at four locations. It corrects negative clock variation. This formula from another chip is not treated as a universal GAF algorithm for the G2 sensor.

The significant setter order is GAF parameter request → GAF bias request → mask/disable → accuracy read/temperature handling → conditional negative correction. ROM IRQ start configuration also remains. Thus this host function **does not replace completion of prior on-demand services or their full RAM effects**. The existence of calculated values is not a reason to clear busy or assert ready.

The GAF patch array is 52 bytes, with a separate loader setting patch base and patch point. It was not executed or translated because ISA, ROM call targets, and correspondence to the G2 version were not verified. The array's existence alone does not make it a full sensor ROM or GAF execution model.

## Conditions of use and unknowns

The repository root LICENSE is BSD-3-Clause and the driver C header contains a separate permission notice. The GAF patch definition header, however, contains wording restricting use, reproduction, and distribution without a separate agreement. The root license is not assumed to resolve terms for every file; this work was limited to private preservation and static inspection. The patch was not copied into Blackwall source.

The official AN-000478 PDF found by search was inaccessible through the web tool, and its direct URL returned HTTP 404. Local pdftotext was also unavailable. Since the document could not be read, ROM/SRAM sizes or behavioral claims from search snippets were not included as verified results. General patents and search results with the same GAF name were not used as evidence of the target sensor execution specification.

## Next work

Compare the [clock variation and derived values](imu-clock-variation-contract.md) already stored by the original G2 ARM setter with this host function's input/output addresses, widths, and calculation order. The objective is to separate existing ARM calculations from effects remaining in sensor ROM. Even if they match, retain `CalculationSupported=false` and strict result access until the full effects of requests 2/4 are established. Do not pass natural boot with another fusion algorithm or arbitrary initial values.

Verification material is outside Git in `simulator/gaf-new-execution-evidence-01/`. The 10 checks in `verify.py` verify only provenance, call order, and array size. A blob check that failed due to an extra trailing newline on first save was preserved in the initial report; it was rechecked after removing one byte only when the expected blob matched. Test counts are not added to progress.
