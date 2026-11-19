# Renode Initial Power and Reset-Shadow Assumptions

Status: Two existing Unicorn virtual conditions were connected to Renode M55 and execution boundaries compared. Actual G2 power state, reset state, and full boot were not validated.

## Differences from the Apollo4 model

In the pinned [Apollo4 power controller source](https://github.com/renode/renode-infrastructure/blob/042a58285ee91453f99d31f19e8aa140102ec540/src/Emulator/Peripherals/Peripherals/Miscellaneous/AmbiqApollo4_PowerController.cs), the first MCUPerformanceControl default is 0x9, and req/ack/status are stored as tags. Do not treat this as implementing actual ACK transition logic for that register. Some MEMPWREN bits also describe cache banks, unlike Apollo510's NVM1/ROM configuration. Matching addresses with [Apollo510 definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/CMSIS/AmbiqMicro/Include/apollo510.h) alone does not justify reusing the entire power controller unchanged.

`BlackwallG2StartupFixture` currently handles only the following two assumptions. Other accesses are passed to the existing strict guard and stop execution. No instructions were added to or patched in original firmware.

| Selection | Supported scope | Unsupported |
| --- | --- | --- |
| --power-mode lp/hp | Four-byte read at 0x40021000 returns 0xd/0x16 respectively | Writes, partial reads, voltage, ACK transitions, frequency changes |
| --reset-latch VALUE | Read of a 13-bit virtual input at 0x4000885c | Actual reset occurrence/detection, other addresses/widths |

The reset shadow allows only the observed write clearing bit 2 from an existing value with bit 1 set. Do not generalize it as an arbitrary write-one-to-clear register. The reset-status meaning of this address remains a hypothesis based on binary and public HAL comparison. Do not describe virtual initial values as obtained from an actual device. The two options are independent and both disabled by default.

Reset restores allowed state to its initial virtual value and clears counters. Reports retain selected assumptions, read/write counts, final latch value, `hardware_verified=false`, `power_transitions=not-modeled`, and `hypothesized-reset-status-shadow`. Selecting HP does not change the Renode CPU's virtual MIPS.

## Six actual-image combinations

Each image was run with explicit LP/HP and reset shadow=2.

| Input | Mode | Next stop address/width | PC |
| --- | --- | --- | --- |
| Stock 2.3.0.24 | LP, HP | 0x40024000 / 4-byte read | 0x54639c |
| Stock 2.4.0.24 | LP, HP | 0x40024000 / 4-byte read | 0x570d70 |
| Faceclaw 38 | LP, HP | 0x40024000 / 4-byte read | 0x54639c |

All recorded one power read, one latch read, zero latch writes, final latch=2, and one first unsupported access. The next address in the table is watchdog CFG; execution stops without returning a value. There were no unverified engine messages.

Existing Unicorn was given the same core assumptions, power modes, and latch=2. That runner uses an already verified exact initial-delay-loop summary; Renode executes the ARM loop itself. All six combinations matched raw image hashes and next address, width, and PC. This compares that boundary, not full execution equivalence, actual time, or power consumption.

Some initial two-second runs ended host-window-ended during the initial delay loop. They were retained and not counted as successes. The later six runs used an explicit five-second cap and all reached the table's boundary. The tool default is two seconds and allowed maximum five seconds. All reports have installable, boot_verified, and hardware_validated false.

Original records are outside Git at `Blackwall/simulator/renode-startup-*-*-latch-02/`; cross-comparison is in `unicorn-renode-startup-fixture-comparison-01/comparison.json`.

## Fixture tests run on the actual engine

Sixteen cases in `verify_renode_mmio_guard.py --with-startup-fixtures` passed: seven existing strict-guard cases and nine covering normal LP/HP values, power partial-read/write rejection, normal latch read, allowed clear/readback, invalid write, partial read, and neighboring-address rejection.

For allowed accesses the later RAM sentinel changed; for rejected accesses the initial sentinel was preserved. Result values and model read/write counts were compared too. This validates fixture contracts and stop behavior, not actual Apollo510 power operation. Results are retained in `renode-startup-fixture-verification-01/report.json`.

```sh
python3 tools/run_renode_main_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-renode-startup" \
  --power-mode lp --reset-latch 2 --wall-run-seconds 5
python3 tools/verify_renode_mmio_guard.py \
  "$HOME/Library/Application Support/Blackwall/simulator/new-startup-fixture-check" \
  --with-startup-fixtures
```

Environment and default runner limitations follow the [main test](renode-main-probe.md). Next was reviewing how much of existing Renode watchdog models could be reused for clock, register, interrupt, and reset behavior. Actual glasses were not accessed.

The [Renode watchdog model](renode-watchdog-model.md) was subsequently connected. Existing Apollo4 IRQ and counter-only limitations were confirmed on the actual engine and a limited model built with Renode timers.
