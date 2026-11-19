# Renode Initial HAL Register Storage Model

Status: Previously observed Unicorn stored values and 24 public reset values were connected to Renode. It is enabled only with explicit `--hal-startup-storage` and requires memory-startup and reset-shadow fixtures. Default is OFF. This does not implement the full actual HAL, clocks, voltages, or valid device calibration.

## Scope and evidence

`BlackwallHalStorage` in `tools/renode-strict-mmio.cs` supplies the following. It allows aligned four-byte reads and only the listed stored values; other addresses, values, and widths stop execution.

| Register / address | Virtual initial value | Allowed stored values |
| --- | --- | --- |
| CLKGEN MISC / 0x40004044 | 0 | 0, 0xfbbfc0 |
| CLKGEN CLKCTRL / 0x40004120 | 0 | 0 |
| MCUCTRL AUDADCPWRDLY / 0x40020448 | 0x200 | 0x200, 0x400 |
| MCUCTRL PWRSW0 / 0x4002037c | 0x80 | 0x80, 0x40000080 |
| MCUCTRL PWRSW1 / 0x40020380 | 0 | 0, 0x10000, 0x11000 |
| PWRCTRL TONCNTRCTRL / 0x400211a0 | 0 | 0, 0x3e80000 |
| PWRCTRL LPOVRTHRESHVDDS / 0x400211a4 | 0 | 0, 0x320 |
| PWRCTRL LPOVRHYSTCNT / 0x400211a8 | 0 | 0 |
| PWRCTRL LPOVRTHRESHVDDF / 0x400211ac | 0 | 0, 0x1c2 |
| PWRCTRL LPOVRTHRESHVDDC / 0x400211b4 | 0 | 0, 0x258 |
| PWRCTRL LPOVRTHRESHVDDCLV / 0x400211bc | 0 | 0, 0xfa |
| STIMER HALSTATES / 0x40008858 | 0 | 0, 0x5af00000 |
| Twelve addresses in public trim/reset catalog | Catalog reset word | Writes prohibited |

Sources are existing [runner analysis](simulator-runner-status.md), [trim/reset evidence](../hardware/power/trim-reset-fixture.md), and public HAL commit `61b293a49db34030c545f99101f7ebf6a3050314`. Pinned catalog SHA-256 is `0be186eab9db2c72cdc2fb8b82d72b2498aab90b5817843538d583c231ee9366`. `verify_trim_reset_catalog.py` rechecked the 12 reset words and original source hashes, fields, and masks. HTML/header differences recorded in the catalog remain valid; they do not mean every ABI matches.

Clock frequency, oscillator readiness, ADC conversion, voltage, switching, TON counter/comparator, and clock-mux recovery are not implemented. Requests to enable TON LP override are also rejected. The public HALSTATES definition is distinguished from the G2 reset-shadow hypothesis at adjacent address 0x4000885c. Reports retain the catalog hash, `valid_calibration=false`, and `hardware_verified=false`.

## Verification

Two successful-sequence tests were first confirmed to fail on the existing implementation (`renode-hal-storage-red-01/`). After adding the model, 42 distinct selected tests passed.

- `renode-hal-storage-verification-01/`: 37 total, including seven existing strict-guard tests, all reads and allowed-storage sequences, unsupported writes to 24 addresses, partial accesses, neighboring addresses, and option OFF.
- `renode-hal-storage-sequence-verification-01/`: seven tests strengthening read/storage sequences with direct comparison of each value, plus rejection of writes equal to reset values, rejection of TON activation, and existing revision/Info1/ROM-state regressions.

Two normal sequences overlap between reports. In the final sequence, guest code compares each readback with expectations and the host independently checks values and read/write counts for each of the 24 registers. This does not claim every other full suite was rerun for this revision.

## Actual main execution

Six LP/HP conditions were run for stock 2.3.0.24, stock 2.4.0.24, and Faceclaw 38 research images. Shared inputs were reset shadow=2, watchdog, reset-controller, startup controls, MRAM provenance, zero Info1 metadata, revision 0x23, SPOT storage, memory startup, and the new option. Main memory protection remains enabled by default.

| Input | Mode | Next unimplemented read / width | PC |
| --- | --- | --- | --- |
| Stock 2.3.0.24 | LP, HP | 0x400211c8 / 4 | 0x489606 |
| Stock 2.4.0.24 | LP, HP | 0x400211c8 / 4 | 0x4954ee |
| Faceclaw 38 | LP, HP | 0x400211c8 / 4 | 0x489606 |

For all six, raw main hash, stop address, width, PC, and each of the 24 registers' final value and read/write counts matched Unicorn with the same inputs. There were no memory-protection violations or unverified engine messages. This compares implementations under shared assumptions, not actual hardware or timing. Stock 2.4 with the option off retained the previous CLKGEN read / PC 0x4952d4 boundary. boot_verified, hardware_validated, and installable remain false.

Results are retained outside Git in `Blackwall/simulator/renode-hal-storage-*/`; comparison is in `unicorn-renode-hal-storage-comparison-01/comparison.json`.

```sh
python3 tools/run_renode_main_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-main-hal-storage" \
  --power-mode lp --reset-latch 2 --watchdog-model --reset-controller \
  --startup-controls --shadow-info1 mram --info1-metadata-fixture zero \
  --chip-revision-fixture 0x23 --spot-control-storage --memory-startup-fixture \
  --hal-startup-storage --wall-run-seconds 15
```

## Next boundary: MRAMEXTCTRL

The public CMSIS header defines 0x400211c8 as PWRCTRL MRAMEXTCTRL. In pinned stock 2.3/2.4 binaries, the next instructions at the PCs above OR the read value with 0x6 and write it to the same address. This corresponds to header MRAMAUTOWAKEUPCTRL bits 2:1, where field=3 is described as disabling auto wake-up. Distinguish register-control writes from MRAM image-data writes.

Execution in this report stopped at the read boundary. A later [MRAM control test](../hardware/cpu-memory/mram-auto-wakeup-control.md) connected limited value storage; actual wake-up behavior remains unimplemented. Full boot, firmware display, web installation, and physical recovery remain unverified, and the actual glasses were not accessed.
