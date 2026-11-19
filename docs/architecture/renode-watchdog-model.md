# Renode-Based Watchdog Time and Interrupt Model

Status: Selected Apollo510 WDT behavior was implemented using Renode's time engine and checked in independent tests and the actual main initialization segment. This is not validation of physical G2, full boot, or physical reset.

## Why the existing model was not used unchanged

The [pinned Apollo4 model](https://github.com/renode/renode-infrastructure/blob/042a58285ee91453f99d31f19e8aa140102ec540/src/Emulator/Peripherals/Peripherals/Timers/AmbiqApollo4_Watchdog.cs) preserves INTEN as a tag but provides no IRQ output. COUNT also reads a reset timer that runs only when RESEN is set. On installed Renode 1.17.0, a WDTEN=1, LFRC/64, RESEN=0 control confirmed COUNT=0 after 200 ms and no IRQ property. This is not evidence that complete watchdog behavior is reproduced.

Blackwall reuses Renode ClockSource, LimitTimer, GPIO, and NVIC and implements a separate limited model. It did not pass tests by taking the existing interrupt-free model unchanged. It follows CFG, RSTRT, COUNT, interrupt registers, and WDT_IRQn=1 in [Apollo510 CMSIS definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/CMSIS/AmbiqMicro/Include/apollo510.h). Separate C# source is `tools/renode-watchdog.cs`, inheriting the existing strict MMIO guard.

## Scope and assumptions

- Initial CFG=0 is a **virtual disabled state** for comparison with existing Unicorn, not an actual reset value or device observation. It also differs from the existing Apollo4 model default 0x00ffff00.
- Assume LFRC=1024 Hz. CLKSEL 1, 2, 3, and 4 nominally yield 128, 16, 1, and 1/16 counter ticks/sec. Sixteen substeps per counter tick express 1/16 Hz with integer timer frequency. Actual oscillator error, calibration, power domains, and clock gating are unimplemented.
- Only aligned four-byte accesses to CFG, key 0xb2 restart, COUNT, and WDTIEREN/STAT/CLR/SET are supported. CLKSEL=0 stops counting. Eight-bit counter wrap is supported.
- At the INTEN threshold, pending is latched and WDTIEREN gates GPIO IRQ. GPIO connects to NVIC IRQ1. Restart does not automatically clear pending; CLR clears it.
- At the RESEN threshold, record a reset request and pause at a Renode synchronization point. **RSTGEN gating, actual reset, and subsequent boot are not executed.** Instruction/cycle accuracy is not guaranteed.
- Lock, active CFG changes, active zero threshold, XTAL clocks 5/6, partial accesses, and other registers stop execution. An invalid restart key that hardware might ignore also stops this limited model.

Some normal hardware features may therefore be unsupported. Do not equate a stop in this model with an actual device fault. Reports retain the source_clock assumption, `reset_propagation=unsupported`, and `hardware_verified=false`.

## Independent engine tests

Fifteen cases in `tools/verify_renode_watchdog.py` passed.

| Scope | Confirmed result |
| --- | --- |
| M55 IRQ delivery | With an INTEN-only timer: IPSR=17, status=1, COUNT=2, one handler invocation; line deasserts after CLR |
| Counting/clocks | Counts even with reset disabled, CLKSEL=0 stops, four LFRC divisions, eight-bit wrap |
| Restart | Counter returns to zero after 0xb2 and advances again |
| Interrupt state | Pending masking, pending retained after restart, enable/clear, software set/clear |
| Reset request | Pauses with ResetDue=true at nominal count=3; no actual system reset |
| Rejection | Guest completion write does not execute after XTAL clock, partial width, or invalid restart key |
| Upstream control | Under the same counter-only conditions, original model COUNT=0, new model COUNT=3 |

Nominal-time tests validate this model's contract, not physical LFRC. Complete results are outside Git at `Blackwall/simulator/renode-watchdog-verification-03/report.json`. Folders 01 and 02 with initial serialization/console failures are not counted as successes.

## Main integration and six-combination comparison

`run_renode_main_probe.py --watchdog-model` splits the existing large MMIO guard before and after WDT and registers the new model on the WDT page. It adds no default values for other addresses. Six combinations of stock 2.3.0.24, 2.4.0.24, and Faceclaw 38 with explicit LP/HP and reset shadow=2 all passed watchdog initialization and stopped at a four-byte read of RSTGEN CFG (0x40000000). PC was 0x546324 for 2.3/Faceclaw and 0x570cf8 for 2.4.

All had WDT CFG 0x020ce004, CFG reads/writes 3/2, restart/IRQ events 0, and COUNT=0. **At this point WDTEN=0.** This does not mean execution reached a segment where actual main operates an active watchdog. Compared with the existing Unicorn instruction-clock WDT assumption, raw image SHA, next address, width, PC, and CFG matched for all six. Active-timer equivalence between engines and hardware latency were not compared.

Comparison is in `unicorn-renode-watchdog-comparison-01/comparison.json`. Main records are retained in `renode-watchdog-stock24-01/` and `renode-watchdog-*-*-01/`.

```sh
python3 tools/verify_renode_watchdog.py \
  "$HOME/Library/Application Support/Blackwall/simulator/new-watchdog-check"
python3 tools/run_renode_main_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-main-watchdog" \
  --power-mode lp --reset-latch 2 --watchdog-model --wall-run-seconds 5
```

## Headless execution fix

During a 17-second virtual-time test, the console input thread's ConcurrentQueue exhausted the memory limit. The same scenario completed with --hide-monitor. Four Renode tools were changed to emit results through System.Console instead of monitor output; the 15 tests above including long-time tests, M55/M4F controls, 16 existing guard/startup fixture tests, and default main execution were rechecked. The container uses network none and does not publish the headless monitor's internal listener to the host. Do not hide a console error as firmware or peripheral success.

Next was connecting initial RSTGEN configuration. Full boot, display transport, installation, and recovery remained incomplete; actual glasses were not accessed.

Subsequently, [RSTGEN CFG and watchdog gate](renode-reset-controller-model.md) were connected. If the selected controller exists, it evaluates WDREN on request; otherwise it remains unevaluated. In both cases system-reset propagation is still unimplemented and execution pauses at the request boundary.
