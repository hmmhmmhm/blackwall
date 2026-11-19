# Reproducibility of GAF Calculation Effects and Original Consumers

bw381. The first verification unit from bw380 was performed. **Available material cannot reconstruct the actual EDMP calculation effects of requests 2/4.** Do not expand the control model or generate normal initialization with automatic ready. Existing setter evidence was analyzed without original execution or model changes; the next independent task is a shared execution/comparison path for registered candidates and existing communications scenarios.

## Evidence examined

`tools/inspect_gaf_effect_evidence.py` reads 48 normal scenarios (3 originals × 16) from existing isolated ARM setter tests. It checks trace SHA in the existing verification report, original main SHA, and SHA256/Git blob/commit tree of public TDK sources. There was no new ARM execution or physical access. The 132 timeout/error propagation scenarios reuse the [earlier helper contract](imu-gaf-service-contract.md).

Public sources are the [driver](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp.c), [header](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp.h), memmap, and request ID definitions at pinned commit `646f55a6ec119b59d9ebce47af660842b53e5506`. These are source evidence for that version, not verification of actual sensor ROM/behavior.

| Boundary | Observed original behavior | Unknown |
| --- | --- | --- |
| Request 2 | Write 02 to SRAM 0004, RMW/trigger/wait for idle | Complete addresses, values, and algorithm of parameters calculated inside EDMP |
| Request 4 | Write 04 to SRAM 0004, same control/wait | Actual bias calculation results, input dependence, numerical expectations |
| Between requests | No setter SRAM read | Not evidence that internal results do not exist |
| After both requests | A272 mask, 2A disable, idle check, calmag patch/key/configuration writes | Control idle alone cannot verify calculation validity |
| Subsequent SRAM read | 4 bytes at 0x5bc, `EDMP_GAF_SAVED_GYR_ACCURACY` | This evidence cannot determine whether request 4 produced it or it was previously stored |
| accuracy=0 | Write Q16 −273°C (`0000effe`) to 0x6a0 | Synthetic input cannot be generalized to actual sensor state |
| GAF output in operation | Public driver contains FIFO format and quaternion/bias decoding | Decoding does not implement calculation that produces fusion results from samples |

The 0x5bc value in the 48 traces was 0 or 0x89abcdef supplied by the test ABI. Thus setter return 0 or a successful accuracy branch does not prove EDMP calculation success. The first inspector failed because it required temperature initialization in every case. It was corrected to the `accuracy==0` condition in public source and actual traces; the failure cause remains in private verification. Original firmware and model were not changed.

The original setter's calmag patch is 125 bytes; its difference from the 189-byte patch in existing public source was already verified. This patch is not treated as the entire GAF calculation or a sensor ROM replacement program. Public configure documentation explains that EDMP is configured to execute ROM code. The driver/definitions/patch and host traces examined do not contain an algorithm or expected outputs to independently verify the complete internal calculations of requests 2/4. This does not conclude that such material is absent from all public sources.

## Assessment and next path

- Request, RMW, trigger, and pending control were verified in bw379. After closing that work's saved audit, `CalculationSupported=false` and calculation completions remain 0.
- Observable subsequent consumption by the original host setter was narrowed, but sensor-internal calculation effects remain unsupported. Do not complete E05/E12 by filling unknown RAM with 0 or returning ready.
- E05 normal required initialization/app lifecycle, E12 sample/FIFO consumption, and E14 long-term communication failure remain incomplete. Overall progress remains **5/16=31.25%**.
- Do not add more of the same control/timer tests. Resumption requires a specification/code for actual calculation, exact ROM program and execution contract, or independently verifiable input/output and supported effects scope. Do not collect real-device evidence without separate authorization.
- Next is an E15/E16 shared execution path connecting the existing E04 candidate manifest and E13 device communications scenario. The runtime runner currently accepts only `stock24/stock23/cfw`; candidate registration uses separate `run_native_candidate.py --firmware-manifest`. Reuse existing candidate verification/memory protection without copying the two runners. Preserve the same board, inputs, and virtual time; do not overwrite candidate failure with original baseline success.
- Connecting a candidate alone does not complete E15/E16. Retain remaining acceptance criteria including comparison of intended behavioral differences and preserved behavior, and frame/tool lifecycle.

## Reproduction and verification

```sh
python3 tools/inspect_gaf_effect_evidence.py <simulator> <new-output>
```

Verified 48 saved evidence analyses, byte-exact frozen-tool report, and rejection of four semantic negatives that also consistently changed report pins: removal of request 4, unexpected SRAM result read, temperature branch violation, and patch length change. If the output folder already exists, the tool rejects rather than overwriting original evidence. This is not an actual EDMP calculation or new integrated execution test.

Source/trace, inspector, and frozen-result hashes are preserved in private `simulator/gaf-effect-evidence-01/{report.json,verification.json,manifest.json}`. The previous bw379 audit was closed as `gaf-on-demand-saved-audit-03/report.json`. The unit 156 results have identical JSON values but are not byte-exact due to differing top-level key order; three native audits are byte-exact.
