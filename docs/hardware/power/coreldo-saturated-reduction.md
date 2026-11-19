# Saturating Subtraction Storage for Core LDO Trim

Status: actual correction-helper arithmetic analyzed, with a policy allowing one field write at the exact initialization stage connected to two executors. Actual voltage, valid manufacturing calibration, and power readiness remain unverified.

## Actual code and calculation

The [PCM2.0 before-enable helper](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/am_hal_spotmgr_pcm2_0.c) in public HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` subtracts from cached original core trim under `g_bOrigTrimsStored`. The same-version header's subtraction constant is 7, and CMSIS CORELDOACTIVETRIM field has position=0, mask=0x3ff. Source SHA and Git blob were compared.

Both stock versions and Faceclaw binaries compare the cached value with 8; if at least 8 they subtract 7, otherwise select 0, then insert it in the lower ten bits of the current LDOREG1 word:

```text
reduced_trim = max(cached_trim - 7, 0)
next_word = (current_word & ~0x3ff) | reduced_trim
```

`tools/probe_coreldo_reduction.py` verifies exact bundle hash and CRC, then runs the original ARM helper independently. It checks PC-relative flag/cache/register addresses and subtraction/BFI instructions, restricting execution to that function. The function body is not replaced with Python calculation.

For each image, 2,058 cases passed, 6,174 total:

- flag=true: 10-bit cached inputs 0..1023 × two current words (0, 0x6d3d4) = 2,048.
- flag=false: five boundary cached inputs × two current words = 10.

Each return value, current word, preservation of bits outside the field, MMIO read/write counts, and function return were checked. This is arithmetic testing across the bit range, not evidence that 1,024 manufacturing calibrations are actually valid. CPU is an approximate Unicorn M4 model, not full M55 board verification.

## Storage policy

`--coreldo-reduction-storage` is OFF by default in both CLIs. It requires buck start and public trim fixture. Unicorn uses `simulator_coreldo.py`; Renode uses an independent controller sharing existing register state.

Only one aligned four-byte write to LDOREG1 (0x40020080) is allowed when all conditions hold:

1. Read traces exist for all 12 public reset-cache targets.
2. Ordered override is finished and buck start is exactly stage 2.
3. Requested value matches subtraction calculated from the initial fixture's cached trim.
4. Bits outside the current word's lower ten are preserved.
5. This policy has not already written.

Read traces are a limited model cache witness, not proof of valid manufacturing calibration or complete RAM cache accuracy. Actual firmware helper's flag condition is separately executed by original code. Missing cache, wrong stage/trim, changes to other fields, duplicates, and partial writes are rejected. Existing trim fixture remains read-only with option OFF; only selection records a write exception. Blocking readiness reads after enable also remains, and no power-ready response is generated.

## Actual main results

Only the new option was added to existing zero Info1, virtual revision 0x23, and initialization conditions. All LP/HP cases across three images stored LDOREG1 once from 0x6d3d4 to 0x6d3cd. Cached trim 980 became 973, preserving other bits. Buck start stage 3 enable request was then recorded, but actual power readiness was not confirmed. The next four-byte write remains unsupported:

| Input | Mode | Next address / requested value | PC |
| --- | --- | --- | --- |
| Stock 2.3.0.24 | LP, HP | 0x40020088 / 0x207c0741 | 0x5bad44 |
| Stock 2.4.0.24 | LP, HP | 0x40020088 / 0x207c0741 | 0x5c22ec |
| Faceclaw 38 | LP, HP | 0x40020088 / 0x207c0741 | 0x5bad44 |

This address is memory LDO LDOREG2. Its word 0x207c0774 was preserved and the write was not authorized. Both engines matched raw main hash, stop address, width, PC, requested value, core trim and register access counts, and buck start state across all six conditions. The actual CLI for the new named scenario was also run. Both executors with option OFF retained the previous LDOREG1 rejection boundary.

## Verification and reproduction

Python runner/controller/profile tests 98 and Renode selected tests 19 passed. Renode comprises seven strict guards, nine new policy tests, and three existing buck-start/readiness-block/HAL regressions. The original helper's 6,174 arithmetic tests and six full-main condition comparisons have different scopes. There were no memory protection violations or unverified Renode messages; boot_verified, hardware_validated, and installable remain false.

Material is preserved outside Git under `Blackwall/simulator/`:

- `coreldo-helper-exhaustive-01/`: original helper arithmetic tests.
- `coreldo-reduction-source-analysis-01.json`: public source conditions, mask, constant.
- `coreldo-reduction-unittest-01/`, `renode-coreldo-reduction-verification-01/`: policy tests.
- `renode-coreldo-reduction-*-*-01/`, `unicorn-renode-coreldo-reduction-comparison-01/`: main runs and comparisons.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/firmware_runner.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  --scenario startup-zero-info1-rev-23-coreldo-reduction-hypothesis \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-coreldo-reduction.json"
```

In Renode, add `--coreldo-reduction-storage` to the [buck start execution conditions](buck-start-request-storage.md). Subsequent [memory LDO configuration](memldo-post-enable-setup.md) was connected; the current boundary is a power-status read. Full boot, firmware display, web installation, and real-device recovery verification remain incomplete; actual glasses were not accessed.
