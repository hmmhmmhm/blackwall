# CRC Optimization with Input Validation Preserved

Measurement scope: `inspect_bundle` on a pinned stock 2.4 bundle on this Mac. It includes CRC validation, input reads, SHA-256, component checks, and limited firmware execution. Python startup/module imports and CLI output-file writes are excluded. This is not a measurement of full boot performance or actual glasses performance.

## Change and equivalence

The previous eight bit operations per byte in `blackwall_package.crc32c` were replaced with a 256-entry table operation. The polynomial, initial value, MSB-first convention, and return value remain unchanged. Four known inputs were compared with `crc32c_msb` from pinned g2flash `845f665`. Hash and CRC checks are not removed, and input validation results are not cached.

Each of the six components in stock 2.3, stock 2.4, and Faceclaw 38 was read by the new validator, and a one-bit payload mutation in each bundle was confirmed rejected with a CRC error. Thirteen package unit tests passed. All ten end-to-end runs produced 7,330,846 instruction boundaries and the same final report SHA-256. Therefore, runs that skipped checks or ended early due to an error were not used for the speed result.

## Measurements

Following `benchmark-checklist`, the implementations were profiled separately and then run five times each in alternating A/B order. The workload was `startup-zero-info1-rev-23-shared-sram-retention-hypothesis`; at the time, the expected normal outcome was to stop at an unimplemented access to 0x40021040.

| Implementation | Median | Minimum–maximum | Runs |
| --- | ---: | ---: | ---: |
| Previous bit loop | 10.99 s | 10.92–11.36 s | 5 |
| Byte table | 7.73 s | 7.52–8.16 s | 5 |

For this input and scenario, the median decreased by about 3.26 seconds, or 30%. The two ranges did not overlap. Do not generalize this improvement to all inputs, platforms, or simulations. There were eight logical CPUs; load averages were 2.56/4.83/7.35 at the start and 4.88/7.93/8.06 at the end. Other apps were not stopped; alternating runs reduced load differences over time. Detailed run values and zero verification failures are in the report outside Git.

In separate cProfile results, per-instruction Unicorn callbacks and firmware execution accounted for a large share. Profiling increases hook costs, so those times were not mixed into the table above. Callback costs remain after the CRC improvement. Do not interpret the CRC improvement as faster CPU emulation or an improvement to the virtual watchdog timeline.

## Reproduction material

The following are retained outside Git in `Blackwall/simulator/package-validation-benchmark-01/`:

- `baseline-blackwall-package.py`, `table-blackwall-package.py`: measured CRC source snapshots
- `run-benchmark.py`, `results.json`: alternating-run script, all measurements, and report hashes
- `baseline-profile.pstats`, `profile-summary.json`: profiler results separate from measurements
- `input-parity.json`: component checks and mutation rejection for three actual inputs
- `simulator-scenarios.json`: catalog at measurement time, matching the SHA recorded in the results

After measurement, an incorrect MIT attribution in a source comment was corrected. g2flash is GPL-3.0; follow the existing NOTICE. The measured snapshot and current CRC function AST were also confirmed identical. The subsequently added MMSOVERRIDE model is not included in the measured workload. Proprietary firmware inputs are separately required in the existing private-inputs path.
