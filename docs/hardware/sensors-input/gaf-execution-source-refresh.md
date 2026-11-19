# Rechecking Public GAF Execution Sources

bw396. Three official TDK repositories were pinned at their current commits to find independent code or expected input/output values that could support normal GAF calculation. **The material read did not provide the complete execution code for request 2/4 calculations.** Existing control/timer tests and ARM execution were not repeated.

| Source | Pinned commit | Finding |
| --- | --- | --- |
| [ICM45608](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/tree/646f55a6ec119b59d9ebce47af660842b53e5506) | `646f55a6…` | Same as the existing pinned commit |
| [ICM45689](https://github.com/tdk-invn-oss/motion.arduino.ICM45689/tree/ebceec8954e4973e2808c99f959f850e81fbca17) | `ebceec89…` | 27 GAF/EDMP-related src files have identical Git blobs to ICM45608. Of 29 related paths, 28 match; the other is an example sketch |
| [Zephyr HAL](https://github.com/tdk-invn-oss/zephyr.hal_tdk/tree/330218a1f25cd58eab3b81eda7510e73525c2e76) | `330218a1…` | Examined icm456xx EDMP code, headers, and memmap; no calculation substitute for GAF requests 2/4 obtained |

API commit/tree responses and 31 related original files are preserved in a private folder. The tree has truncated=false, and Git blob SHA1 and SHA256 were checked for every received file. This checks agreement with the GitHub source, not physical sensor behavior.

## Dependencies remaining despite RAM images

Public distributions contain RAM images for dispatcher, calmag, selftest, all-quaternion, AID, B2S, MRM, and others. A file is not treated as the full sensor ROM merely because its name contains program/image. In the actual source, `inv_imu_edmp_configure` sets IRQ0/1/2 start addresses to the ROM base and +4/+8. The GAF setter executes requests 2/4 before loading the calmag patch. Thus reading the public patch does not reproduce the earlier ROM service calculations.

Parsed length and hash for each image were also recorded. This investigation did not obtain the full sensor ROM image, an execution contract for its ISA, or an independent numerical oracle for requests 2/4. It does not claim these are absent from all other public sources. GAF initial values, FIFO decoding, and request control are distinguished from actual fusion calculation.

## Boundary for the next experiment

Keep `CalculationSupported=false` and strict result-access checks for the nominal path. Limit a new virtual fault experiment to **EDMP not executing after a request, leaving busy asserted**. This model generates neither nominal ready nor calculation RAM. The objective is to observe the original ARM's actual timeout, error return, and subsequent caller to see how the app handles initialization failure.

Build the fault model as a separate opt-in component/tool and preserve existing nominal/profile and frozen audits. Do not force original branch/R0/TCB/SP. Distinguish the virtual fault assumption that previously initialized SRAM persists from verification of actual hardware failure behavior. Continue to stop strictly at the next unsupported transaction. Results cannot establish normal boot or completed calculation.

Pinned originals and material: private `gaf-source-refresh-01/{sources.json,sibling-comparison.json,array-inventory.json,manifest.json}`. Overall 7/16 (43.8%) and API 3/6 remain unchanged. No physical access, Astra/subagents, or external publication occurred.
