# Final audit: original boot → main → screen

bw-0550, 2026-11-16. All eight original conditions of `original-boot-screen-v1` were verified. **8/8 = 100% is the completion rate for this goal**, not for full chipset fidelity. The goal, denominator, and supported combinations were not reduced.

| Condition | Verification evidence |
| --- | --- |
| OB01 Original identification | Recompared the full SHA, size, addresses, and SP/reset vectors of stock 2.4 boot/main with the current files |
| OB02 Original boot execution | Actual M55 sequence from boot reset through CRT/FPU/C/data initialization to boot C main; also confirmed in both final normal runs |
| OB03 Protection and functional contracts | Verified boot read-only policy is included exactly in the final model; existing eight-condition evidence retained; actual strict boundary for unsupported marker |
| OB04 Original selection/handoff | One cleared-marker case, selected address 0x438000, original SP/reset, and actual handoff and main reset; no inference of successful cryptographic verification |
| OB05 Same-board lineage | Compared actual VTOR/active SP/MSP/PSP/CONTROL/xPSR with original handoff; confirmed each bank in both final normal runs |
| OB06 Screen | After original UI/renderer: 576×288 A8, 165,888 bytes, exact guest SRAM at the same point, and personally inspected preview |
| OB07 Repetition/rejection | Configuration, components, and raw frames exact across two final cold runs; unknown metadata produced main/frame 0; host preflight rejected corrupted/truncated images |
| OB08 Reproduction/audit/cleanup | Pinned profile, derive/run/audit-existing, 14 boundary tests, reaudit of 30+30 normal and 29 rejection conditions, and inspection of owned processes/artifacts |

## Reproducible results

See [one-command execution and independent audit](original-boot-reproduction.md), the [pinned profile](../data/original-boot-stock24-profile.json), [first screen](original-boot-first-screen.md), and [repetition and failure inputs](original-boot-repeat-and-rejection.md). The implementation is `tools/run_original_boot_screen.py`, and the execution runtime is `tools/renode-original-boot-runtime.py`. Proprietary firmware and the existing frozen model are referenced as private assets and are not distributed.

The two final normal runs are `original-boot-cli-native-bw548-02` and `original-boot-cold-repeat-native-bw549-01`. Their raw frame SHA is identical: 81200ab102c507de6a5853a33086958d16bcb93168ff631ee76b6c8c391adba2. Each also matches guest RAM. We do not claim full instruction-count or virtual-time equality. The raw and contrast-enhanced PNGs of the last frame were personally inspected, confirming the clock and the “No news available / Add new sources in the app” panel.

The original handoff loads 0x2007fb00 into PSP, the current SP under CONTROL2. MSP 0x2007fa90 is retained. The host did not force MSP or PC into place. CPU, time, and full SRAM were identical before and after the explicit HP10→167MIPS functional cadence for the UI transition.

The unknown marker was blocked by guard 1 at PC 0x42e582/address 0x7fe000/read 4. Handoff/main/UI/frame and external activation inputs were 0. Passing that test means the expected rejection succeeded; it is not a successful boot or actual recovery authentication.

## Cleanup and preservation

The 116 folders and 178 owned journals belonging to the goal were checked against the current Docker inventory. Zero owned containers remained, and zero inspected ELF/object/DLL/pyc files or duplicate guest boot/main and cadence comparison artifacts remained. Other work's containers, browsers, and assets were not touched. Canonical originals, models, source/hashes, reproduction commands, native logs, final guest RAM/frame, audits, and failure analyses were retained. Earlier initialization-boundary limitations and failure records remain as they stood at the time.

For the reproduction CLI's initial host preview O(n²) issue, the record of interrupting only postprocessing with 130 after native execution ended was preserved, and the processing was made linear. Postprocessing evidence was recovered without rerunning the existing native execution, and the final runner's two normal cold runs were subsequently verified separately through completion. The interruption was not counted as a normal CLI completion.

The canonical record is private `simulator/original-boot-final-audit-bw550-01/report.json`. Actual verification results are recorded in its `source-and-evidence-audit.json`, `cleanup-and-process-audit.json`, `normal-a/report.json`, `normal-b/report.json`, `unknown-marker/report.json`, and `unit-tests.log`.

## Scope

Execution starts at the original bootloader reset, not an actual Boot ROM reset. The test covers one stock 2.4 virtual temple and explicit virtual touch/UART/GAF, constant ADC, reference GPU, and cadence functional profiles. Physical glasses were not modified. Other boot/main combinations, high-fidelity reproduction of the full Boot ROM, chipset/GPU ISA, sensor fusion, RF and power, and actual installation/recovery certification are separate. Further scope is determined by new user instructions.
