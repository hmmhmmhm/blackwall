# Correspondence Between Original G2 ARM and New Host Correction

bw460. The applicability of the formula in the [new official correction source](gaf-host-correction-evidence.md) to G2 was checked using 48 existing transaction records and additional original ARM runs. **The tested G2 setter did not execute that correction, and there is no basis for implementing normal GAF by adding a formula from another sensor.** Normal GAF and natural display remain incomplete; overall progress remains 10/16=62.5%.

## Address and execution differences

The memmap of official ICM45687 commit `dffaee833d41b1f786c7a19c4f01f4d7a2dd1e98` was additionally read and checked against the blob in the existing pinned Git tree. The four regions written by the new function and corresponding names in the existing ICM45608 are:

| Host correction write | ICM45687 | Existing ICM45608 |
| --- | --- | --- |
| GYR_DT_US | 0x400 | 0x4a0 |
| GYR_DT_US-8 | 0x3f8 | 0x498 |
| COVARIANCE_ACC+8 | 0x410 | 0x4e0 |
| COVARIANCE_ACC+4 | 0x40c | 0x4dc |

Corresponding names do not establish identical ROM algorithms or numerical units. Existing source/trace inspectors were reused to check 3 originals × 16 = 48 saved runs and source pins. These saved records are isolated setter tests supplied with synthetic ready/accuracy, not evidence of normal sensor calculation.

Additionally, six signed trim values `-128,-123,-1,0,1,127` were each run through the original stock 2.4/2.3/Faceclaw setters. The actual ARM function was byte-identical to the existing one; only I/O leaves used the existing synthetic ABI. Each run confirmed requests 2 → 4, actual return 0, and preservation of SP, original SRAM, and input structure. None wrote to the four ICM45608 regions above, and all transactions were the same except for the selected trim-byte write. Therefore no corresponding execution of the new correction was observed for this input set. This does not prove its absence from every other configuration or caller.

The previously verified legacy input was also rerun once per original and matched all existing transactions exactly. Final captures comprise 18 boundary runs + 3 controls = 21. The first two attempts stopped at the legacy comparison, executing 7 and another 14 runs, respectively. The 35 actual total execution attempts are distinguished from the 21 final captures. All were isolated M7; no Renode natural main or EDMP execution was added.

The initial control failure was a test input error that substituted getter seed `0x5a` as the actual trim byte. The actual trim produced by the getter was `0xf6`. Failed transactions were preserved, and exact agreement was confirmed after restoring the original buffer's trim. Neither firmware nor expected transactions were modified.

## Conclusion and subsequent boundary

The new function describes limited correction after requests 2/4 complete on a different part. Those writes are absent from the existing G2 host path, so adding them would create different behavior instead of reproducing the original. The formula was not added to the model, and ready, PC, TCB, and original branches were not changed. ODR/period storage already performed by the G2 setter is distinguished from sensor-internal derived calculations.

This comparison closes the applicability review of the new host function. Do not extend the same negative-trim/wait variants further. Resuming normal GAF still requires an exact execution specification/code or independent numerical results and effects scope. Separate sensor/input contract work can proceed before obtaining that evidence, but E05/E09/E12 cannot be marked complete.

Evidence outside Git: `simulator/gaf-host-arm-correspondence-01/{probe.py,report.json,baseline-mismatch.json,inv_imu_edmp_memmap.h,manifest.json}`. The probe imports only the `run` definition from the existing frozen function using AST and does not rerun the entire historical timeout test. Original bundle/main and SRAM pins were rechecked. No physical access, model changes, external publication, or subagents occurred.
