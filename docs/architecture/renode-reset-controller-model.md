# Reset-Controller CFG and Watchdog Enable Bit

Status: Storage of two RSTGEN CFG bits and gate evaluation for watchdog reset requests were connected. Complete system reset, post-reset state restoration, and reboot were not implemented.

## Model and evidence

[Pinned Apollo510 CMSIS definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/CMSIS/AmbiqMicro/Include/apollo510.h) define RSTGEN CFG at 0x40000000 bit 0 as BODHREN and bit 1 as WDREN. They state WDREN also requires watchdog timer RESEN. WDREN is not treated as bit 0.

`tools/renode-reset-controller.cs` permits aligned four-byte CFG reads/writes and values 0..3 only. Virtual initial CFG=0 is an input for comparison with the existing Unicorn fixture, not an actual reset value or device state. Brownout input itself is unimplemented. Read/write counts, CFG, and WDREN are recorded with hardware_verified=false.

The watchdog model may optionally reference this controller. On reaching the reset threshold it records ResetDue and evaluates WDREN at that moment. If the controller is absent, evaluated is false. `reset_allowed_by_gate=false` with `reset_gating_evaluated=false` must not be interpreted as a blocked judgment: the gate is unevaluated/unconnected.

Whether the gate allows or blocks, the current model pauses at the request boundary. This does not reproduce subsequent counter behavior on an actual device with the gate disabled. Reset propagation after RSTGEN, retention, reset-cause latch, and next boot remain unimplemented. SWPOI/SWPOR and related operations in particular stop at the strict guard rather than executing. All assessments are virtual register contracts, not physical-device validation.

## Independent engine tests

Ten selected cases in `renode-reset-controller-verification-01/report.json` passed: two regressions for existing IRQ/unconnected-reset boundaries and the following eight.

| Test | Result |
| --- | --- |
| CFG=0 | Watchdog reset gate blocked |
| CFG=1 | Brownout only enabled; watchdog gate blocked |
| CFG=2 | Watchdog gate allowed |
| CFG=3 | Watchdog gate allowed |
| Reserved-bit write | CFG preserved, stops at first access, subsequent guest completion write not executed |
| SWPOI key write | Stops without executing virtual reset |
| Partial-width CFG read | Stops |
| 0 → 1 → 2 → 3 configuration | Final CFG=3, four writes, WDREN=true |

After restructuring the collector into explicit controller-present/absent branches, IRQ, gate-allowed, and configuration-roundtrip cases were rerun and retained in `renode-reset-collector-regression-01/`. This does not claim the entire unselected watchdog suite was rerun for this revision.

## Next boundary in actual main

`run_renode_main_probe.py --reset-controller` separates the RSTGEN page from the existing MMIO guard and connects the two objects when the watchdog model is also selected. Runs without this selection retain the previous unimplemented boundary. Other peripherals are not filled with default zero.

Three images were run with explicit LP/HP, reset shadow=2, watchdog, and reset-controller.

| Input | Mode | Next read address/width | PC |
| --- | --- | --- | --- |
| Stock 2.3.0.24 | LP, HP | 0x40021004 / 4 | 0x488fca |
| Stock 2.4.0.24 | LP, HP | 0x40021004 / 4 | 0x494eb2 |
| Faceclaw 38 | LP, HP | 0x40021004 / 4 | 0x488fca |

This address is DEVPWREN. All six combinations had RSTGEN CFG=2, one read and one write, and WDREN=true. Watchdog CFG=0x020ce005 enabled WDTEN and RESEN, with one restart and COUNT=0. Execution stopped at the next unimplemented access, and no reset request had yet occurred. Do not extend this to long-duration active-watchdog operation or actual reboot validation.

Against Unicorn with the same conditions, raw main hash, next address, width, PC, RSTGEN CFG, and WDT CFG matched for all six combinations. Active clock models differ between engines, so this does not imply timing equivalence. Every report has installable, boot_verified, and hardware_validated false.

Executions are retained outside Git at `Blackwall/simulator/renode-reset-*-*-01/`; comparison is in `unicorn-renode-reset-comparison-01/comparison.json`.

```sh
python3 tools/run_renode_main_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-main-reset-controller" \
  --power-mode lp --reset-latch 2 --watchdog-model --reset-controller --wall-run-seconds 5
python3 tools/verify_renode_watchdog.py \
  "$HOME/Library/Application Support/Blackwall/simulator/new-reset-gates" \
  --case gate-disabled --case gate-brownout-only --case gate-watchdog --case gate-both
```

Subsequent DEVPWREN, debug, core-power, and WIC condition integration is recorded in [startup control tests](renode-startup-controls.md). Actual glasses were not accessed.
