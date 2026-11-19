# Buck Status Branch and Single-Sample Tests

Status: branch tests supplying one explicit power-state sample were added to two engines. The ACT path matched across six LP/HP combinations of three images. Initial OFF/LP comparison failed because Renode lacked cache support; the subsequent [instruction memory functional model](../cpu-memory/coherent-instruction-cache-model.md) supplemented default blocking and confirmed 12-combination agreement with the optional model. This does not verify actual power readiness, full boot, firmware display output, or installability.

## Meaning of the current stop

The `VRSTATUS` read after earlier [memory LDO configuration](memldo-post-enable-setup.md) is not simply a power-ready wait. Actual ARM code in three mains checks an original trim-storage flag, extracts SIMOBUCKST bits 4–5, and compares against 3. If different, it skips this helper's correction write and returns.

| State | Value in pinned public header | Stock 2.4 LP Unicorn result |
| --- | --- | --- |
| OFF | 0 | Skips correction write and stops at cache-control write `0xe000ef50` |
| LP | 2 | Same stop as OFF |
| ACT | 3 | Stops at VREFGEN4 correction write `0x4002004c` |

Value 1 is not defined in the public enum and cannot be selected. Buck LP and the existing `--power-mode lp/hp` condition are separate virtual inputs.

Evidence is `apollo510.h` and `am_hal_spotmgr_pcm2_0.c` from pinned `hal_ambiq` commit `61b293a49db34030c545f99101f7ebf6a3050314`, plus actual instructions from the three images. Existing source SHA-256 was rechecked and enum, mask `0x30`, and position 4 compared. The public `vddc_vddf_tempco()` condition and VDDF correction explain the observed branch. The entire public function, build options, and timing are not claimed identical to the original binary.

Helper starts are `0x5ba518` for stock 2.3/Faceclaw and `0x5c1ac0` for stock 2.4. The state-address literal, extraction/comparison instructions, inactive return branch, and VREFGEN4 address literal in a 168-byte range were checked. Actual main with ACT attempts to write 54, subtracting 10 from the public reset-assumed trim 64. The requested word is `0x1fefb6`; this write is not yet allowed.

## Optional fixture scope

New `--buck-status-fixture off|lp|active` is unselected by default. Selecting a value requires explicitly enabling the memory LDO configuration model.

- Supply it only after buck enable request stage 3 and memory LDO configuration stage 2 complete.
- Supply selected word `0`, `0x20`, or `0x30` for one DWORD read at `0x40021108` only.
- Assume remaining status fields are 0 and state this in the report.
- Subsequent reads, partial-width reads, writes, and missing prerequisites stop at the existing strict boundary.
- With the option off, the earlier `VRSTATUS` read block remains.

This fixture supplies input for software branch comparison. It is not a model of automatic power-state transitions, actual hardware response to commands, delay, voltage, or manufacturing calibration. One read followed by blocking does not substitute for power-state provision across full startup.

## Verification and unresolved difference

A total of 111 Python regression/policy checks and 13 Renode synthetic guest checks passed. The latter include 10 new status samples and three existing boundaries: all three statuses, blocking each second read, byte/halfword blocking, write blocking, and blocking when memory LDO is incomplete.

Actual main comparison with ACT matched across three images × LP/HP, six combinations, on:

- Main hash, stop PC/address/width/requested value.
- One status sample, word `0x30`.
- Values and read/write counts of 12 public trim fixture words.

Stop PC is `0x5ba598` for stock 2.3/Faceclaw and `0x5c1b40` for stock 2.4, address `0x4002004c`, requested value `0x1fefb6`. The write was not applied. No Renode memory protection violations or unexpected engine warnings occurred.

OFF/LP ran on both engines for stock 2.4 LP but **agreement verification failed**. Unicorn stops at the first cache-control write to `0xe000ef50`. Renode reports an unhandled-write warning and unsupported instruction-cache enable warning, then continues. The runner detects these warnings and fails with exit 1. A later PPB stop is not accepted as the correct first-access boundary. Next investigate the functional meaning of this cache behavior and the engines' different handling, then provide consistent restrictions or an explicit model.

With the status option disabled, stock 2.4 LP regression retained the prior `VRSTATUS` read block at PC `0x5c1ad0` and register/memory policy state. Existing profiles without the status option were unchanged.

## Reproduction

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/firmware_runner.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  --scenario startup-zero-info1-rev-23-buck-status-active-hypothesis \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-buck-status-active.json"
```

For OFF/LP comparison replace `active` in the scenario name with `off` or `lp`. In Renode add `--buck-status-fixture active` to the memory LDO execution conditions. Use new output paths. Pinned images and original main are preserved outside Git.

Evidence under private simulator:

- `buck-status-branch-analysis-01.json`: branch/literal and public source checks for three images.
- `buck-status-unittest-01/`, `renode-buck-status-verification-01/`: regression and synthetic guest tests.
- `unicorn-buck-status-stock24-lp-*-01.json`, `buck-status-native-stock24-01/`: actual execution and failure warnings for three states.
- `buck-status-active-comparison-01/`: ACT six-combination comparison.
- `buck-status-disabled-regression-01/`: option-unselected regression.

All boot/hardware/installable verification flags are false. The overall goals of web-installable CFW, recovery boot readiness, and integrated simulator/display connection remain in progress; actual glasses were not accessed.
