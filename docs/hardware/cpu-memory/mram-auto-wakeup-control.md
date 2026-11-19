# Limited Storage Model for MRAM Auto Wake-Up Control

Status: connected the public MRAMEXTCTRL reset word and writes observed in actual main to both runners. Actual MRAM wake-up, power, calibration, delay, and content changes are not implemented. The default option is OFF and no physical glasses were accessed.

## Public source and binary evidence

Used material from pinned HAL commit `61b293a49db34030c545f99101f7ebf6a3050314`:

- `apollo510.h`: PWRCTRL MRAMEXTCTRL offset `0x1c8`, address `0x400211c8`.
- `pwrctrl_regs.html`: MRAMAUTOWAKEUPCTRL reset field=1, position=1, mask=`0x6`. The other three fields and reserved bits reset to 0, making the complete reset word `0x2`.
- At the end of `am_hal_pwrctrl_low_power_init` in [am_hal_pwrctrl.c](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/am_hal_pwrctrl.c), code writes 3 to the field under APOLLO5_GE_B1. Comments about bit interpretation after B1 and wake-up delay are HAL descriptions, not measured results.

`tools/verify_mram_control_sources.py` pins the three original SHA-256 values, combines reset fields and masks, and checks the offset using actual clang M55 `_Static_assert(offsetof(...))`. Earlier binary analysis showed actual stock/Faceclaw instructions OR `0x6` into the read word and write it back to the same address. With initial value `0x2`, this produces `0x6`. The public reset value is virtual input; it is not assumed to match the actual device after bootloader execution.

## Implementation boundary

The Unicorn option is `--mram-auto-wakeup-storage`; Renode uses `--mram-control-storage`. The latter requires explicit HAL startup storage; the former requires a power-mode fixture.

Only aligned four-byte reads, restoring the current value, and storing `0x2` → `0x6` are allowed. Repeatedly storing `0x6` leaves the final value unchanged. Restoration `0x6` → `0x2`, clock-gate bit changes, hard-recall/dynamic/reserved bits, partial accesses, and adjacent addresses are rejected. Other field semantics and actual MRAM behavior are not arbitrarily treated as successful.

This stores an MRAM **control register value**. It is not writing MRAM image data or a flash operation. Main write protection and unwritten ITCM execution checks still apply. A subsequent voltage-override write also stops if outside existing allowed values.

## Tests and diagnostic improvement

Before implementation, initial-value and storage test failures were confirmed. The final Unicorn runner/profile suite passed 88 tests and the Renode optional suite passed 24. Renode covered seven strict guards, 14 MRAM conditions, and three existing Info1/ROM-state/HAL-read regressions. Tests include value storage, repeated/reverse writes, invalid bits/width/address, and option OFF.

During engine comparison, found that Unicorn omitted the requested value of a rejected MCUCTRL write from its report. Reproduced this with a failing regression test and fixed it to record the actual value. Final comparisons include requested value as well as address, PC, and width. The first comparison folder missing this diagnostic was preserved as incomplete material.

## Actual main results

Applied LP/HP separately to two stock versions and the Faceclaw 38 research image. Only MRAM control storage was added to prior HAL startup conditions. All six recorded one MRAMEXTCTRL read, one write, and final value 6 before stopping at the next boundary.

| Input | Modes | Next unsupported write / width | Requested value | PC |
| --- | --- | --- | --- | --- |
| Stock 2.3.0.24 | LP, HP | `0x40020060` / 4 | `0x2e000` | `0x48961c` |
| Stock 2.4.0.24 | LP, HP | `0x40020060` / 4 | `0x2e000` | `0x495504` |
| Faceclaw 38 | LP, HP | `0x40020060` / 4 | `0x2e000` | `0x48961c` |

This address is MCUCTRL VRCTRL. Raw main hash, next address, width, PC, requested value, MRAM value, and access counts matched in both engines across all six cases. The actual CLI for Unicorn's new named scenario was also run with stock 2.4 LP. Both runners retained the existing MRAMEXTCTRL read boundary with the new option off. There were no memory protection violations or unverified Renode messages. `boot_verified`, `hardware_validated`, and `installable` remain false.

Results are outside Git at `Blackwall/simulator/renode-mram-control-*/`; source checks are in `mram-control-source-verification-01/`, unit logs in `mram-control-unittest-01/`, and the final comparison in `unicorn-renode-mram-control-comparison-02/comparison.json`.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/firmware_runner.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  --scenario startup-zero-info1-rev-23-mram-control-hypothesis \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-mram-control.json"
```

For Renode, add `--mram-control-storage` to the [HAL storage execution example](../../architecture/renode-hal-startup-storage.md). Reproduce public-source checks with:

```sh
python3 tools/verify_mram_control_sources.py \
  "$HOME/Library/Application Support/Blackwall/simulator/upstream/hal-ambiq-61b293a" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-mram-source-check"
```

## Next analysis target

The VRCTRL request `0x2e000` adds SIMOBUCKPDNB bit 17 to the previous ANALDO configuration `0xe000`. It appears to correspond to the public HAL `buck_ldo_override_init` sequence, but actual voltage and DeepSleep effects are unverified. The later [override sequence storage test](../power/buck-ldo-override-sequence.md) connected ten observed stages; actual voltage and DeepSleep effects remain unimplemented. Full boot, display, web installation, and physical recovery verification remain incomplete.
