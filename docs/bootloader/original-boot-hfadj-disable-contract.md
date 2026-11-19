# HFADJ disable during original boot

Status: bw532 in progress. This is not a numerical or frequency model of HFRC calibration.

In the pinned AmbiqMicro.Apollo_DFP 1.6.0 Apollo510 SVD, HFADJ address is 40004020, reset value 25b800, and HFADJEN bit 0=0. Original function 426fd6 reads this register, clears bit 0, and stores it. The original ARM instructions execute this behavior without injecting a separate success return or branch.

The model adds only writes of the same disabled word as this reset value to existing opt-in HAL storage. Enabling calibration, changing gain/target, reserved bits, and partial writes are rejected. No calibration-complete/active bit is created in clock status.

This initial value is an explicit entry profile based on DFP register-reset metadata, not a measurement of actual G2 HFADJ after Boot ROM. The official [Apollo510 datasheet's reset-level description](https://contentportal.ambiq.com/documents/20123/2877485/Apollo510-SoC-Datasheet.pdf) also distinguishes CLKGEN/HFADJ initialization scope by reset type. Do not expand this to verification of physical initial values across all warm/reset paths.

## Evidence

- `private:simulator/boot-hfadj-source-bw532-01/source-proof.json`: actual SVD SHA, address/initial value/bit evidence. A different Apollo510L SVD was not used.
- `change-proof.json` in the same folder: SHA comparison showing only one register entry added.
- `private:simulator/boot-hfadj-red-bw532-01/report.json`: reproduction of existing original HFADJ read block.
- `private:simulator/boot-hfadj-green-bw532-01/report.json`: 14 checks passed, including disabled-word preservation/repetition and unsupported-write blocking. This is a C# register-contract test; actual ARM is distinguished in separate native records.

## Original execution result and cleanup

Execution ended at virtual limit after 20,092,252 original instructions and 2.0092252 virtual seconds. Code/system protection, all strict guards, and CFSR/HFSR were 0. Final PC 40 was an original delay loop, R0=3a7df7, LR 41d20f. Delay entries were 2027, returns 2026, with last entry count 4166642 in a new delay. It is not judged a guard stop or infinite hang; model and counters remain unchanged while the execution budget is expanded in the next diagnosis. Boot manager/handoff/main/frame have not been reached. Authoritative record: `private:simulator/original-boot-hfadj-native-bw532-01/frontier-proof.json`.

An identical 149773-byte boot dump was removed and all three runs' owned Docker processes confirmed removed. Compilation output was removed with containers; source, logs, pinned model, hashes, and commands remain.
