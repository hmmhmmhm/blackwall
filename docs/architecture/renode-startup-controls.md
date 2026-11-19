# Renode Initial Power and Debug Control Tests

Status: Four limited initial conditions from existing Unicorn were connected to Renode. This does not implement actual power transitions, sleep/wakeup, or full boot.

## Selected assumptions and stop conditions

`--startup-controls` is used with explicit `--power-mode lp` or `hp` and is off in default execution. The startup fixture in `tools/renode-strict-mmio.cs` handles only the aligned four-byte accesses below; other values, widths, and addresses stop at the existing strict guard.

| Address | Virtual initial condition | Allowed behavior |
| --- | --- | --- |
| 0x40021004 DEVPWREN | Peripheral power OFF | Read 0, write 0 |
| 0x40021008 DEVPWRSTATUS | Peripheral power OFF | Read 0 only |
| 0x40020250 MCUDBGCTRL | Debug port OFF | Read 0, write 0 |
| 0xe001e300 CPDLPSTATE | Core domain ON | Read 0, write 0 |
| 0x4002021c WIC | Initial stored value 0 | Read, store 0 or 1 |

Addresses and register definitions derive from pinned Apollo510 CMSIS material and existing runner analysis. This does not mean these values were observed on the user's glasses. In particular, storing a WIC value does not reproduce wakeup behavior, and storing CPDLPSTATE does not perform a core-power transition. Source versions follow [reuse research](emulator-reuse-research.md).

## Test results

Thirty-one tests in `renode-startup-controls-verification-01/report.json` passed: seven existing strict guards, nine power/reset fixtures, and 15 new control conditions. Alongside normal reads/storage, checks confirmed first-access recording and no subsequent guest completion write on power-on, status write, debug enable, core transition, unsupported WIC value, and partial-width access. This is not physical-device validation.

Actual main was executed with LP/HP, reset shadow=2, watchdog, reset-controller, and the new option selected.

| Image | Mode | Next unimplemented read / width | PC |
| --- | --- | --- | --- |
| Stock 2.3.0.24 | LP, HP | 0x400201bc / 4 | 0x48934e |
| Stock 2.4.0.24 | LP, HP | 0x400201bc / 4 | 0x495236 |
| Faceclaw 38 research image | LP, HP | 0x400201bc / 4 | 0x48934e |

All six runs recorded one device-power read, two debug reads and writes each, one WIC read and write each with final value 1, and one PPB core-power write. RSTGEN CFG=2, watchdog CFG=0x020ce005, and COUNT=0; no IRQ/reset request had yet occurred. The next boundary is SHADOWVALID. Valid Info1 or actual device calibration data was not arbitrarily supplied.

Compared with Unicorn execution under identical conditions, raw main hash, stop address, width, PC, and control-access counts above matched for all six combinations. Since both engines use the same assumptions, this match is not independent evidence of actual chip behavior or timing accuracy. boot_verified, hardware_validated, and installable remain false.

Results are retained outside Git in `Blackwall/simulator/renode-startup-controls-*-*-01/` and `unicorn-renode-startup-controls-comparison-01/comparison.json`.

```sh
python3 tools/verify_renode_mmio_guard.py \
  "$HOME/Library/Application Support/Blackwall/simulator/new-startup-control-tests" \
  --with-startup-fixtures --with-startup-controls
python3 tools/run_renode_main_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-main-startup-controls" \
  --power-mode lp --reset-latch 2 --watchdog-model --reset-controller \
  --startup-controls --wall-run-seconds 5
```

A later [memory policy](renode-memory-policy.md) blocks main writes and execution of unwritten ITCM. Full CFW display, BLE, sensor, and recovery validation remains incomplete; actual glasses were not accessed.
