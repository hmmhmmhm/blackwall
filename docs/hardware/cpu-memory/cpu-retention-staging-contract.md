# CPU Retention Configuration and Original Return

bw-0416. During stock 2.4 execution on a virtual reset path, the `CPDLPSTATE=0x22` configuration function returned to its original caller. This model implements **storage of retention configuration registers only**; deep-sleep preparation, actual entry, and wake have not yet executed. Original app return and E05/E06 completion are unverified, with overall progress remaining 8/16 = 50.0% at that point.

## Meaning and original code

In the pinned [CMSIS M55 header](https://github.com/ARM-software/CMSIS_6/blob/45dab712ad84f8cbbf2b7bfc089c19088507df6f/CMSIS/Core/Include/core_cm55.h), CPDLPSTATE places RLP/ELP/CLP at bits 8/4/0 respectively. The pinned [Ambiq power header](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/am_hal_pwrctrl.h) defines RET for ELP and CLP as 2. Therefore `0x22` configures RLP 0, ELP 2, CLP 2. It does not mean actual power gating occurred.

Preserved SDK/CMSIS files after reverifying the existing source manifest and SHA-256. In actual ARM for stock 2.4, stock 2.3, and Faceclaw, each original sleep function reads the three byte constants `[0,2,2]`, follows branches preserving existing RLP and ELP=OFF, and calls the config setter. The binary's packed argument layout was not assumed to use the default size of SDK C enums.

| Original | Config setter | Write PC | Return PC |
| --- | --- | --- | --- |
| Stock 2.4 | `0x4956ac` | `0x4956e2` | `0x44df60` |
| Stock 2.3 / Faceclaw | `0x4897c4` | `0x4897fa` | `0x44d670` |

Static verification covered all three originals; the new native execution was performed only for stock 2.4. Do not report that the new retention path was executed and verified for the other two.

## Optional model

`cpu_retention_staging_model.py` extends only the selected strict model's existing CPU sleep class. The shared default core file was not changed. Constructor store/return PC pairs default to 0; only the new board explicitly supplies stock 2.4's pinned addresses.

A `0x22` write is stored only after checking the actual guest CPU's store PC and LR and the three SRAM argument bytes `[0,2,2]`. Direct host calls and missing/unaligned address pairs are rejected. Existing checks for values 0/`0x11` and normal-sleep control-read/flush order remain. Stage count is cleared on Reset.

Original main, branches, return values, and WFI were not modified. An owned observation callback at the config setter return PC stopped the machine **before the subsequent power-state update call**. This does not constitute completed power/sleep preparation and does not broadly allow later deep-sleep flushes or register writes.

## Actual result and checks

Observed stock 2.4 original reset → virtual connection/ATT time consumption → external NVIC SYSRESETREQ → original reset vector → initialization → retention configuration → return at `0x44df60`. Virtual time from reset entry to return was 6.185548 seconds, with stage 1, CPDLP `0x22`, and zero architectural faults/strict guards. Initialization was still underway; do not describe this as normal boot completion or stable operating time.

- Passed 26 boundary audit checks. The previously unsupported `0x22` run also passed 26 checks in the current audit while retaining its failure-boundary verdict.
- Passed 30 unit checks covering default unselected behavior, rejection of host writes and incorrect PC pairs, reset, and existing normal-sleep sequence/flush regressions. The prior 29-check result was also preserved.
- Rejected three counterexamples changing values, stage count, and return observation together in log/JSON, and one counterexample judging a historical failure run as stage success.
- Passed 14 progress-management checks. Pinned-input regeneration and frozen audit comparison are recorded in the private manifest.

Evidence: private `simulator/cpu-retention-staging-native-02`, `cpu-retention-staging-unit-02`, and `cpu-retention-staging-research-01/manifest.json`. Original firmware and SRAM/NOR are outside Git. No physical access, flash, OTA, Astra/subagent, or external publication occurred.

## Disk failure and recovery

During the first native run the host disk filled and the Docker socket disappeared. The execution handle ended with a cleanup error and OrbStack status was Stopped. Partial data from the first run was preserved but not used as success evidence. Only redownloadable pip/uv caches were cleaned.

Separately, compared contents of 4,888 pinned main/SRAM fill/ITCM fill copies and atomically replaced 4,878 with APFS copy-on-write copies. All paths, byte hashes, file modes, and mtimes were preserved; hard links were not used. Originals, confidential backups, and execution results were not deleted. Comparison/replacement records and free space before and after were retained privately.

After starting OrbStack, confirmed no containers remained and ran a new execution using the same pinned image ID/arm64. This native tool gained a 1 GiB host free-space check before preparation. It does not guarantee against disk exhaustion during execution caused by other work.

## Next boundary

Analyze the next original deep-sleep preparation call, `power_state_update`, and its power/clock/retention conditions; connect actual WFI, IRQ wake, and return to the original caller. Only after that should original app event reprocessing and reset-state lifetime be checked for E06 completion. Do not overstate simple `0x22` storage as completed actual sleep or app recovery.
