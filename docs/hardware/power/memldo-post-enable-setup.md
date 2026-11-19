# Memory LDO Configuration After Enable Request

Status: order-limited storage of two fields connected to Unicorn and Renode. Both stock versions and Faceclaw main pass this configuration and stop at a power-status read. Actual power stabilization, full boot, firmware display output, and device installation were not verified.

## Relationship between binary and public source

After verifying SHA-256 and CRC of three pinned bundles, original main was analyzed. Function start is `0x5bad3a` for stock 2.3.0.24/Faceclaw and `0x5c22e2` for stock 2.4.0.24. All three 28-byte functions have SHA-256 `8ba3e01b253aa983f4b8ccf3e8c0831be516bf2045fda2cf65a63161ffd88937`. The function returns 0 after two read-modify-writes.

| Address / field | Observed change | Result under public reset assumption |
| --- | --- | --- |
| `0x40020088` LDOREG2.MEMLDOACTIVETRIM | Set lower six bits to 1 | `0x207c0774` → `0x207c0741` |
| `0x400201b0` D2ASPARE.MEMLDOREF | Set bits 15–16 to 2 | `0` → `0x10000` |

Public sources are `apollo510.h` and `am_hal_spotmgr_pcm2_0.c` in pinned `zephyrproject-rtos/hal_ambiq` commit `61b293a49db34030c545f99101f7ebf6a3050314`. Existing pinned hashes of local files were rechecked and field masks/positions and two assignments compared. Twelve public reset values were also reverified with the existing verifier. These are not manufacturing calibration data.

Public `am_hal_spotmgr_pcm2_0_simobuck_init_aft_enable()` contains a 100 µs delay, status check, and subsequent power-state handling in addition to the two settings. The original binary's 28-byte function lacks those operations. **Matching the two field settings is distinct from whole-function equivalence.** Public-source delay/power-readiness conditions are not reported as executed in this binary.

## Execution model limits

New `--memldo-setup-storage` defaults OFF and requires explicit Core LDO reduction model selection. Both engines allow only:

1. Prior Core LDO reduction applied and SIMOBUCK enable request at exactly stage 3.
2. One DWORD write each, LDOREG2 first and D2ASPARE second.
3. All bits outside those fields preserve current stored values.

Wrong order, width, value, prerequisite, or rewrite after completion stops at existing strict MMIO. Allowed values are stored in existing register objects, so readback and write counts agree. The default read-only trim fixture exception is explicit in reports selecting this option.

After enable request, `VRSTATUS` read remains **blocked before the existing reset fixture**. Neither readiness nor status 0 is arbitrarily returned; analog power, calibration, and stabilization time are not modeled.

## Verification scope

| Check | Result and scope |
| --- | --- |
| Original ARM helper execution | 1,136 cases per image, 3,408 across three passed |
| Python regression/policy/probe | 106 tests passed |
| Renode synthetic guest | 17 passed: 13 memory LDO and four existing boundaries |
| Actual main engine comparison | All six combinations, three images × LP/HP, matched |
| Option OFF regression | Existing LDOREG2 write stop and state retained for stock 2.4 LP |

Original helper checks execute 1,024 cases of 256 combinations of six-bit/two-bit fields with four surrounding-bit pattern pairs, plus 112 one-hot/inverted patterns for each bit outside the fields. They do not exhaust all 32-bit word pairs. Each case checks address, width, order, value of two reads/writes and return. The engine is an approximate Unicorn Cortex-M4 model, not proof of Cortex-M55 or analog behavior. Independently written Thumb fixtures also tested positive cases and rejection of address, field, and assignment-value tampering.

Actual main stores LDOREG2=`0x207c0741` and D2ASPARE=`0x10000` once each, then stops at `0x40021108` read. PC is `0x5ba528` for stock 2.3/Faceclaw and `0x5c1ad0` for stock 2.4. Both engines matched main hash, PC, address, width, values and read/write counts of 12 trim words, and buck start state. No Renode memory-protection violations or unexpected engine warnings occurred. Code at this boundary extracts status bits 4–5 and compares with 3. Meaning of full wait, failure, and subsequent paths is the next analysis target; no success response is injected to advance.

The subsequent [buck status branch test](buck-status-branch-fixtures.md) confirmed this point corrects only when ACT. A single-sample test with explicit status selection was added; the existing unselected boundary remains.

## Reproduction and preservation

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/probe_memldo_setup.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-memldo-helper"

"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/firmware_runner.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  --scenario startup-zero-info1-rev-23-memldo-setup-hypothesis \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-memldo-main.json"
```

In Renode, add `--memldo-setup-storage` to [Core LDO execution conditions](coreldo-saturated-reduction.md). Use new paths for outputs. The private simulator directory outside Git preserves:

- `memldo-helper-exhaustive-01/`, `memldo-source-analysis-01.json`, `memldo-public-reset-verification-01.json`
- `memldo-unittest-01/`, `renode-memldo-verification-01/`
- `renode-memldo-*-*-01/`, `renode-memldo-stock23-lp-02/`
- `unicorn-renode-memldo-comparison-01/`, `memldo-disabled-regression-01/`

stock23 LP 01 is initial material where execution succeeded but aggregation script referenced an incorrect key. 02, with execution-condition reporting completed, was used in final comparison; initial material remains preserved. Hardware/boot/installable verification indicators are false in all reports. Web distribution, recovery boot, CFW integration readiness, full boot, and display connection remain incomplete.
