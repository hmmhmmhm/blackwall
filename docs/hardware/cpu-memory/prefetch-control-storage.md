# PFCR Control Storage and D-Cache Information Boundary

Status: defined PFCR field storage was added to both runners. Twelve combinations of two stock versions and Faceclaw, buck OFF/LP, and main LP/HP stopped at the same next D-cache selection write. Actual prefetch requests, cache size, performance, full boot, and display integration were not verified.

## Original code and public sources

Original ARM masks each of three configuration bytes in RAM to three bits, adds ENABLE, and writes PFCR. Actual main execution requests `0x369`. This matches pinned HAL defaults `ui8MaxOutTransactions=6`, `ui8MaxLookAhead=6`, and `ui8MinLookAhead=4`.

| PFCR field | Position/width | Observed default field value |
| --- | --- | ---: |
| ENABLE | bit 0 | 1 |
| MIN_LA | bits 1–3 | 4 |
| MAX_LA | bits 4–6 | 6 |
| MAX_OS | bits 7–9 | 6 |

The defined mask is `0x3ff`, address `0xe001e004`. Evidence is from these pinned sources:

- [Ambiq HAL cachectrl](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_cachectrl.c): default configuration and PFCR assignment before D-cache enable.
- [CMSIS Cortex-M55 definitions](https://github.com/ARM-software/CMSIS_6/blob/45dab712ad84f8cbbf2b7bfc089c19088507df6f/CMSIS/Core/Include/core_cm55.h): MEMSYSCTL base, PFCR offset 4, field positions and masks.

Verified Git blob and SHA-256 for two HAL source files and reused the existing CMSIS structure-offset compilation check. Upstream files, pinned commits, and hashes are preserved in a private manifest. This does not claim the full public HAL function and all actual firmware behavior are equivalent.

## Model contract

`--prefetch-control-storage` defaults to OFF. Unicorn requires the core-domain adapter and Renode the startup-controls adapter. This option does not implement a prefetch engine.

- The initial value is **unknown**. Reads before the first explicit DWORD write are blocked.
- Only DWORD writes of values `0..0x3ff` are stored; reserved-bit writes and other widths are rejected.
- After a write, the current word can be read. An explicitly written 0 is a valid stored value.
- Reports include the stored word, read/write counts, and unimplemented physical effects.

The ability to store defined bit combinations does not mean every combination is valid or useful on actual hardware. Actual prefetch reads, memory transactions, latency, and power are not reproduced. Unknown state at creation and one execution were tested; full system reset was not verified.

## Next D-cache boundary

After PFCR, original code checks CCR.DC and attempts to write 0 to CSSELR. Earlier Renode handled some cache geometry registers as tag values, so continuing unchanged could have treated an arbitrary default as actual cache size.

Accesses to selection/size information `0xe000ed80..0xe000ed87` and unsupported cache maintenance command writes now stop. Geometry reads abort at the guard after the NVIC virtual read; the value is not accepted as valid geometry for subsequent code. Actual main stops earlier at a write to `0xe000ed84`. No arbitrary cache size is supplied.

This does not claim a guard fully implementing every maintenance-command read or every SCS access. Unsupported behavior outside scope fails execution through existing warning checks.

## Results checked

- **131 relevant Python regression tests passed.** This is the specified module set, not all repository tests.
- **16 native cache/geometry guard cases passed.** Three new geometry selection/read/maintenance-write cases were confirmed failing before the fix.
- **13 native PFCR access cases passed:** 11 PFCR and two existing boundary cases. One guest exhaustively stored and compared 1,024 words.
- The Python storage model also stored and compared 1,024 words and checked rejection of initial reads, reserved bits, access widths, and adjacent addresses.
- Results from both engines matched for **three actual main images × main LP/HP × buck OFF/LP = 12 combinations**.

Actual main wrote PFCR `0x369` once with zero reads. It stopped on a DWORD write of 0 at the next address `0xe000ed84`; PC, requested value, the existing 12 trim words, and read/write counts matched. I-cache functional model state remained, with no Renode memory-protection violations or unexpected warnings.

The option-OFF regression retained the prior `0xe001e004` stop for stock 2.4 LP. Under ACT, PFCR remained uninitialized and the existing VREFGEN4 write stop remained. Do not extend these two regressions to every image and path.

## Reproduction and tracking

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/firmware_runner.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  --scenario startup-zero-info1-rev-23-buck-off-prefetch-storage-hypothesis \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-prefetch-main.json"
```

For buck LP, change `buck-off` to `buck-lp` in the name. For Renode main execution, add `--prefetch-control-storage` to the existing coherent I-cache conditions. Use a new output path.

Task ID is `bw-0002`, parent criterion S3. Completion of this task does not imply all of S3 is complete or that the product acceptance rate increases. No glasses were accessed.

Private simulator evidence:

- `prefetch-source-audit-01.json`: comparison of pinned sources, fields and defaults, with existing offset-check references.
- `renode-dcache-boundary-red-01/`: failure before the fix.
- `renode-icache-verification-02/`, `renode-prefetch-verification-01/`: synthetic guest checks.
- `prefetch-main-comparison-01/`: Python regressions and comparison of 12 actual-main combinations.
- `prefetch-regression-01/`: option OFF and ACT path preservation checks.

Keep original/candidate images and keys outside Git. The web installation gate and hardware approval boundaries remain unchanged.
