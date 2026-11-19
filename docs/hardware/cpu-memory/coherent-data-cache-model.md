# Functional Data Memory and D-Cache Initialization

Task `bw-0024`, partial progress toward overall criteria S3 and S6. The full main app loop and integrated display remain incomplete; installation gate and hardware approval requirements were unchanged.

## Evidence and model scope

Section 3.2, printed page 28 of the [Ambiq Apollo510 datasheet 1.1.0](https://contentportal.ambiq.com/documents/20123/2877485/Apollo510-SoC-Datasheet.pdf/6f7b4ae1-6630-d80c-1e17-ec7445b0509e?download=true&t=1780184793760) specifies a 64 KiB, four-way D-cache with 32-byte lines and supported policies. Comparing fields in pinned CMSIS 6.3.0 `core_cm55.h` and initialization/clean loops in `armv7m_cachel1.h` yielded 512 sets and model CCSIDR `0xf03fe019`. This is a documentation-based simulation profile, not a value read from G2. Compared the path after PFCR configuration in SDK `am_hal_cachectrl_dcache_enable()` with original main execution.

Explicit `--coherent-dcache-model` handles size selection/query and set/way invalidate, clean, and clean/invalidate. CSSELR supports only L1 data selection 0. Reads before the first selection, other cache selections, reserved bits, partial accesses, and command-register reads are blocked. By-address maintenance commands were also unsupported at this stage.

Before first enable, the model checks that all 2,048 distinct set/way entries have been initialized. This is a model verification rule, not a claim that actual CPUs automatically block such errors. Repeating the same entry or only cleaning does not satisfy enable conditions. Re-enable after disable requires new initialization.

Memory uses the engines' coherent memory. Physical cache lines, dirty data, delay, replacement, power, and DMA incoherence are not reproduced. Renode CPU's actual cache bits are masked and guest-visible I/D enable states are stored separately. The default unselected path remains blocked.

## New boundary reached by actual main

Compared 12 combinations of pinned stock 2.3.0.24, 2.4.0.24, and Faceclaw 38 with main LP/HP and first buck OFF/LP fixtures in both engines. All reached matching PC, MMIO accesses, and cache counters. Original main performed 2,048 invalidates and 2,048 cleans, queried and selected geometry twice each, enabled I/D cache, then stopped on a second buck status read at `0x40021108`. The existing one-shot status fixture was not automatically reused; the power response remained unimplemented.

Stock 2.4's next PC was `0x4947ac`. Refer to the comparison report for other image PCs and hashes. There were no Renode memory-protection/system-control violations or unexpected engine messages. This is not verification of normal boot, physical cache behavior, or physical device compatibility.

The initial two-second run ended at its normal limit during an initial delay. After checking and matching the existing comparison's 15-second condition, execution continued. Original main instructions were not modified.

## Verification and reuse

- Passed 109 final Python tests. One cache-fixture test includes 34 subconditions.
- Checked 34 native cache conditions: 16 default/I-cache and 18 D-cache.
- The first 18 native D-cache cases were built with M55 instructions. Python rejected the fixture's DLS instruction. A fixture for comparing register behavior across engines was built with scalar Cortex-M4 instructions and reverified in 18 conditions on native M55. Actual main and native M55 CPU were retained.
- Option OFF retained the existing CSSELR stop. The ACT condition stopped at the same `0x4002004c` VREFGEN4 write as the saved earlier result and did not reach PFCR/D-cache initialization.

The comparison tool's initial reuse check omitted two reset/watchdog source files. Corrected the bundle definition instead of treating this as an actual source difference. Reused four completed native conditions after checking inputs, selection conditions, pinned source, and result hashes. Reran four Python conditions to leave new execution receipts. One stock 2.4 preliminary result was also reused.

The first Python fixture regression failed because it did not account for the new D-cache switch, sufficient instruction limit, and combined CCR state. After fixing those and separating DLS rejection, final regressions passed. A short 500k-instruction observation and incorrectly chosen ACT expected address in auxiliary regression were preserved and corrected; comparison with the actual existing ACT result confirmed a match without rerunning.

During this investigation, I manually assembled a path for the stock 2.4 LP/OFF result and looked up a nonexistent copy directory, then incorrectly described it as an error in a historical comparison row. Independent review confirmed the actual historical row already correctly referenced `renode-prefetch-stock24-lp-off-01`. The incorrectly created `prefetch-pointer-correction.json` was corrected separately with `prefetch-pointer-correction-superseded.json`. Original evidence and test results were unchanged.

## Reproduction and next steps

```sh
python3 tools/firmware_runner.py /private/stock-2.4.0.24.bin \
  --scenario startup-zero-info1-rev-23-buck-off-coherent-dcache-hypothesis \
  --output /private/new-data-cache-report.json
python3 tools/compare_dcache_startup.py /private/verified-bundles /private/new-comparison
```

On the current Mac, use Python from private `simulator/venv-02`. The following were preserved outside Git under `~/Library/Application Support/Blackwall/simulator/`:

- `dcache-verification-01`: official PDF, source hashes, red/green, final Python regression, fallback, and correction.
- `dcache-native-final-01`, `dcache-native-scalar-01`: native default/I-cache and D-cache fixtures.
- `dcache-main-comparison-02`: 12 combinations, hashes of both results, and source hashes.
- `dcache-main-stock24-lp-off-01` and `02`, `dcache-main-comparison-01`: preliminary and interrupted execution material.

Next investigate buck status responses before and after requests using public HAL and original call order. Do not simply increase read counts or always return ready. Then connect remaining initialization to reach the actual app loop (S6) and display boundary (D3).
