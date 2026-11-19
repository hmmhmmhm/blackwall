# Renode Chip Revision and SPOT Configuration Storage

Status: Four revision conditions and limited ACRG/VRCTRL storage previously analyzed in Unicorn were connected to Renode. This is not validation of actual silicon revision, voltage, or power stabilization.

## Model scope

`--chip-revision-fixture 0x21|0x22|0x23|0x24` supplies only aligned four-byte reads of CHIPREV (0x4002000c). SIPART and upper bits are assumed zero. It does not select or detect the revision of an actual G2. Writes and partial accesses stop execution.

`--spot-control-storage` supplies only storage/readback of these values:

| Register | Virtual initial value | Allowed stored values |
| --- | --- | --- |
| ACRG, 0x40020028 | 0x78 | 0x78, 0x79 |
| VRCTRL, 0x40020060 | 0 | 0, 0x8000, 0xc000, 0xe000 |

Definitions, observed firmware prefix, and public HAL evidence are recorded in [SPOT classification analysis](../research/spot-classification-research.md). This model does not implement analog power, SWE gating, voltage stabilization time, or valid trim. Unsupported values, widths, and addresses stop at the strict guard; `analog_power=not-modeled` and `hardware_verified=false` are recorded. Both options are off by default; main execution requires `--startup-controls`.

## Verification results

Two tests expecting successful CHIPREV and ACRG reads first failed on the existing implementation (`renode-silicon-red-01/`). After model addition, 22 selected tests in `renode-silicon-verification-01/report.json` passed: 19 new revision/SPOT tests and three existing strict-guard/WIC/Info1 regressions. This does not claim the previous full 48-test suite was rerun for this revision.

Six conditions were executed for each stock 2.3.0.24, 2.4.0.24, and Faceclaw 38 research image. Shared inputs were LP, reset shadow=2, watchdog, reset-controller, startup controls, MRAM provenance, and a zero fixture for three Info1 words. All next unimplemented accesses were four-byte reads.

| Revision / storage option | Next address | Stock 2.3 / Faceclaw PC | Stock 2.4 PC |
| --- | --- | --- | --- |
| 0x21 / OFF | 0x40021018, memory power status | 0x488a7c | 0x494964 |
| 0x22 / OFF | 0x40020028, ACRG | 0x489d96 | 0x495c7e |
| 0x23 / OFF | 0x40020028, ACRG | 0x489d96 | 0x495c7e |
| 0x24 / OFF | 0x42003370, unsupplied Info1 word | 0x48 | 0x48 |
| 0x22 / ON | 0x40021018, memory power status | 0x488a7c | 0x494964 |
| 0x23 / ON | 0x40021018, memory power status | 0x488a7c | 0x494964 |

All six runs with storage ON had two ACRG reads and writes each, final value 0x79, and three VRCTRL reads and writes each, final value 0xe000. For all 18 cases, raw main hash, stop address, width, PC, revision-read count, and, when storage was enabled, each register value and read/write count matched Unicorn with identical inputs. This is an implementation comparison under shared assumptions, not evidence of actual power, timing, or normal boot. boot_verified, hardware_validated, and installable are all false.

Results are retained outside Git in `Blackwall/simulator/renode-silicon-*-*-01/` and `unicorn-renode-silicon-comparison-01/`.

```sh
python3 tools/run_renode_main_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-main-silicon" \
  --power-mode lp --reset-latch 2 --watchdog-model --reset-controller \
  --startup-controls --shadow-info1 mram --info1-metadata-fixture zero \
  --chip-revision-fixture 0x23 --spot-control-storage --wall-run-seconds 5
```

A later [memory policy](renode-memory-policy.md) blocked main writes and execution of unwritten ITCM. Subsequent memory-power conditions were connected in [memory startup condition tests](renode-memory-startup.md). Later peripherals and full boot remained incomplete. Physical compatibility of web-install CFW/recovery boot and complete firmware screen generation were unverified. No device access, firmware installation, or external publication occurred.
