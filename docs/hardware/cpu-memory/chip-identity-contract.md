# Chip Information Read Contract and Partial Structure Verification

bw-0131. Extend original execution stopped at MCUCTRL.CHIPPN after RTC using a read-only virtual profile. This work did not query the actual device's chip ID, vendor ID, SKU, or silicon revision.

## Sources and profile

Reviewed the pinned Apollo510 SVD/header and HAL commit `61b293a49db34030c545f99101f7ebf6a3050314`: [MCUCTRL implementation](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_mcuctrl.c), [structure definition](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_mcuctrl.h), and [JEDEC definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/regs/am_reg_jedec.h). New source files were compared against Git blob hashes in the pinned tree. The source is under BSD 3-Clause; commit and SHA are preserved in private `chip-identity-research-01/sources.json`.

`--chip-info-profile source-reset-zero-ids` models only these six words:

| Address | Item | Virtual value |
| --- | --- | --- |
| `0x40020000` | CHIPPN | SVD reset `0x10320080` |
| `0x40020004` | CHIPID0 | Explicit synthetic 0 |
| `0x40020008` | CHIPID1 | Explicit synthetic 0 |
| `0x4002000c` | CHIPREV | Shared with the existing explicit revision fixture; test uses `0x23` |
| `0x40020010` | VENDORID | Explicit synthetic 0 |
| `0x40020014` | SKU | SVD reset `0x002d480f` |

Zero unique IDs and vendor values are not device data. PN/SKU reset values are not guaranteed to be actual device values at main entry either. Follow the source's direction to use SKU/CHIPREV instead of the older CHIPPN size/revision fields. Do not overwrite the existing assumed `0x23` with source reset CHIPREV `0x21`. SIPART, actual hardware revision, case version, and device-specific compatibility remain unknown.

Although the SVD access label is read-write, this model supports only the checked read path. It rejects writes, other widths, and unsupported addresses. This is not a claim that ID registers are unwritable on actual silicon. Without the profile, existing strict behavior remains; selecting it still requires an explicit revision.

## Source and original-code comparison

`analyze_chip_identity.py` compiled the six register offsets, 64-byte public device-info ABI, and eight JEDEC offsets from the original C definitions. It also directly compared literals and RAM/MRAM lookup tables in three pinned originals. The artifact is `private:simulator/chip-info-source-01/report.json`.

The HAL and checked original path read six MCUCTRL values, calculate memory size from the SKU table, then read eight JEDEC values. JEDEC addresses, field positions, and JEP manufacturer bit definitions are in source, but this research did not establish actual Apollo510 part-number values. Do not copy HAL comments about an earlier Apollo generation as current values. JEDEC values were not added to this model.

## Verification results

The 23 isolated checks in `chip-info-unit-01` verified the six values, read-only behavior, shared revision count, widths/adjacent addresses, default strict behavior, and reset. A CLI profile without revision is rejected before input/output/native execution.

`chip-info-main-comparison-01` sequentially ran three originals and one without the model. Original main used its own ARM instructions to store virtual values in a partial SRAM structure and calculate memory sizes. Checked fields in the bounded 64-byte snapshot were:

| Structure offset | Meaning | Observed in all three originals |
| --- | --- | --- |
| `0x00`–`0x14` | PN/ID0/ID1/revision/vendor/SKU | Matches the profile above |
| `0x18` | Qualified | 1, an unconditional constant store by the original |
| `0x20` | ITCM | 262144 bytes |
| `0x24` | DTCM | 524288 bytes |
| `0x28` | System SRAM | 3145728 bytes |
| `0x2c` | MRAM | 4194304 bytes |

These sizes match the source SKU table and current model map. They are not measurements of the actual device's physical memory capacity. Qualified 1 is not a hardware qualification or compatibility verdict. Legacy FlashSize at offset `0x1c` and JEDEC fields from `0x30` onward had not yet been written and were excluded from verification. Do not interpret the remaining captured stack values as chip information or claim the complete structures match.

All three originals stopped strictly at the JEDEC.PID0 (`0xe00fefe0`) read: stock 2.4 PC `0x495fe2`, stock 2.3/Faceclaw 38 PC `0x48a0fa`. Return from the information query function was not yet observed. Without the model, the existing CHIPPN read/PC `0x495f64` and selected counters remained. Stock 2.3/CFW board, model, result, and probe were the same; only main length differed in `run.py`.

Compare original hashes, actual logs, source, and partial structure separately. At this stage UART TX/ISR and I2C/CQ were 0; full boot, integrated display, and physical device verification remained incomplete. An independent review within the same GPT-6 family covering source and standalone tests found no additional material issues. Astra and a separate transcript archive comparison were not used. Product criteria remain 13/29.

## Next boundary

Next, check the source of JEDEC identity values and the scope of a synthetic personality. If actual PN values remain unknown, keep them unknown and distinguish execution with an explicit mock from actual device identification. Do not replace the query function with host code or skip the JEDEC read.

Reproduce with `python3 tools/verify_chip_identity.py NEW_OUTPUT` and `python3 tools/verify_chip_main.py SIMULATOR_ROOT NEW_OUTPUT`. Run static source checks using `tools/analyze_chip_identity.py` in the existing Capstone venv. Pinned private source, bundle, and the prior RTC execution profile are required.
