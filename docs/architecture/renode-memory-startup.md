# Renode Initial Memory Power Conditions

Status: The existing Unicorn limited memory-power, retention, and override model was connected to Renode. It is explicitly selected with `--memory-startup-fixture`, defaults OFF, and requires `--startup-controls`. This is not a measurement of actual device power, calibration, or sleep state.

## Provided state and stored values

Definitions and existing binary analysis follow the [memory-power model](../hardware/cpu-memory/memory-power-model.md). Public Apollo510 HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` and pinned Renode Infrastructure `042a58285ee91453f99d31f19e8aa140102ec540` are used. Pinned source/hashes were checked and 32 actual clang M55 offsetof checks rerun, including the seven register locations below. Matching addresses do not establish behavioral compatibility.

| Address / register | Virtual initial value | Allowed behavior |
| --- | --- | --- |
| 0x40021014 MEMPWREN | 0x3f | Read, store current value again, one ROM OFF 0x3f → 0x1f |
| 0x40021018 MEMPWRSTATUS | 0xcf | Read only; 0x4f after ROM OFF |
| 0x4002101c MEMRETCFG | 2 | Read, store 0..3 |
| 0x40021024 SSRAMPWREN | 7 | Read, store 7 again |
| 0x40021028 SSRAMPWRST | 7 | Read only |
| 0x4002102c SSRAMRETCFG | 0x7e38 | Read, store values within mask 0x7e3f |
| 0x40021040 MMSOVERRIDE | 0x1b0c | Read, store 0x1b0c/0x30c/0xc |

All accesses are aligned four-byte operations. Initial conditions assume TCM/NVM/ROM ON, cache OFF, and shared SRAM ON. The ROM-OFF status transition assumes zero delay. Repeated OFF still counts as one transition; ROM reactivation and other domain transitions are rejected. Partial widths, unsupported bits, status writes, and other addresses stop at the strict guard.

Retention and override implement storage/readback only. Sleep entry, wakeup, actual retention, voltage, stabilization, isolation, and ROM contents are not reproduced. The main runner's [memory-protection policy](renode-memory-policy.md) remains enabled by default.

## Independent tests

Two state-read cases were first confirmed to fail on the existing implementation (`renode-memory-startup-red-01/`). After model addition, 42 selected tests passed:

- `renode-memory-startup-verification-01/`: seven strict guards and 28 new memory read/write/rejection cases.
- `renode-memory-startup-transition-verification-01/`: five cases including status read after ROM OFF, ROM restoration rejection, and existing WIC/Info1/revision regressions.
- `renode-memory-startup-option-verification-01/`: two cases including option OFF and repeated ROM OFF.

Each test checks actual guest readback, register values/access counts/ROM transition count, and whether guest completion writes are prevented after a stop. This is not physical-hardware validation. It does not claim all other full suites were rerun.

## Actual main and engine comparison

LP/HP were applied to stock 2.3.0.24, 2.4.0.24, and Faceclaw 38 research images. Shared inputs were reset shadow=2, watchdog, reset-controller, startup controls, MRAM provenance, zero Info1 metadata, revision 0x23, SPOT storage, and the new memory fixture.

| Input | Mode | Next unimplemented read / width | PC |
| --- | --- | --- | --- |
| Stock 2.3.0.24 | LP, HP | 0x40004044 / 4 | 0x4893ec |
| Stock 2.4.0.24 | LP, HP | 0x40004044 / 4 | 0x4952d4 |
| Faceclaw 38 | LP, HP | 0x40004044 / 4 | 0x4893ec |

The address is CLKGEN MISC. All six cases had one ROM-OFF event, final MEMPWREN 0x1f, status 0x4f, MEMRETCFG 2, SSRAMRETCFG 0, and MMSOVERRIDE 0xc. Counts were MEMPWREN five reads/two writes, status ten reads, MEMRETCFG two reads and writes each, SSRAMRETCFG four each, MMSOVERRIDE two each, and shared power status one read. There were no memory-protection violations or unverified engine messages.

The first five-second HP run ended `host-window-ended` in the ITCM delay loop. That report was retained, and a run with a 15-second window in a new folder reached the next boundary. CLI default remains two seconds; only the allowed range was widened to 0.01..15 seconds. Whole-process timeout of 45 seconds and container resource limits remain. Do not interpret this host time or instruction count as actual G2 performance/timing.

Compared with Unicorn under identical conditions, raw main hash, stop address, width, PC, register values, and access counts matched for all six cases. Unicorn's shared-power read count combines two addresses, so it was compared with the sum of Renode enable/status reads. Both engines use the same assumptions; this is not independent validation of physical power or time accuracy. Stock 2.4 with all options off also retained the existing 0x40021000 / PC 0x495e9c boundary.

Results are retained outside Git in `Blackwall/simulator/renode-memory-startup-*/`; comparison is in `unicorn-renode-memory-startup-comparison-01/comparison.json`. boot_verified, hardware_validated, and installable remain false.

```sh
python3 tools/run_renode_main_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-main-memory-startup" \
  --power-mode lp --reset-latch 2 --watchdog-model --reset-controller \
  --startup-controls --shadow-info1 mram --info1-metadata-fixture zero \
  --chip-revision-fixture 0x23 --spot-control-storage --memory-startup-fixture \
  --wall-run-seconds 15
```

Subsequent CLKGEN and initial HAL storage integration is recorded in [HAL storage tests](renode-hal-startup-storage.md). Full boot, display, web installation, and physical recovery validation remain incomplete; actual glasses were not accessed.
