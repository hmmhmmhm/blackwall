# Order-Limited SIMOBUCK and LDO Override Storage

Status: ten MCUCTRL VRCTRL initialization stages observed in actual main connected to two executors. Voltage, switching, and DeepSleep behavior are not implemented. `complete` means only storage-sequence completion, not that actual device power is normal.

## Source and order

Pinned public HAL `61b293a49db34030c545f99101f7ebf6a3050314` `am_hal_pwrctrl.c: buck_ldo_override_init` and `apollo510.h` were used. This HAL writes SIMOBUCK, core LDO, and memory LDO override bits after their respective settings. The same OR/BIC instruction order was confirmed in actual stock 2.3.0.24, 2.4.0.24, and Faceclaw 38.

After verifying each original main hash, the function's PC-relative literal was checked to point to 0x40020060 and ten operations compared against 14 public-header field masks. Starting from existing completed ANALDO storage value 0xe000 produces:

| Stage | Setting | Stored VRCTRL value |
| --- | --- | --- |
| 1 | SIMOBUCKPDNB | 0x2e000 |
| 2 | SIMOBUCKRSTB | 0x6e000 |
| 3 | SIMOBUCKACTIVE | 0xee000 |
| 4 | SIMOBUCKOVER | 0xfe000 |
| 5 | Clear CORELDO cold-start bit | 0xfe000 |
| 6 | CORELDO ACTIVE, ACTIVEEARLY, PDNB | 0xfe00e |
| 7 | CORELDOOVER | 0xfe00f |
| 8 | Clear MEMLDO cold-start bit | 0xfe00f |
| 9 | MEMLDO ACTIVE, ACTIVEEARLY, PDNB | 0xfe1cf |
| 10 | MEMLDOOVER | 0xfe1ef |

Stages 5 and 8 rewrite the same value with this initial state but are distinct stages executed by actual code. Arbitrary repetition is not automatically approved; it advances a stage only at these positions. HAL's DeepSleep effects are source comments, not actual hardware measurements. Analysis is outside Git in `Blackwall/simulator/buck-override-source-analysis-01.json`.

## Model boundary

Both CLIs require explicit `--buck-override-storage`; default is OFF. Unicorn requires MCUCTRL and SPOT storage models. Renode main also requires explicit SPOT and MRAM control fixtures. Existing base ANALDO storage option behavior remains.

The new sequence starts only at VRCTRL=0xe000. After starting, only the exact next-stage value is allowed; writes before readiness, early override, skipped stages, ANALDO bit changes, and re-entry after completion are rejected. Unsupported partial-width accesses also stop. No other register values or voltage-stabilization success are fabricated. Actual calibration values, power response, and reset/DeepSleep transitions are unimplemented. Main memory protection remains applied.

## Verification

After confirming the complete sequence failed in the existing implementation, the model was added. Final Unicorn runner/profile tests 91 and Renode selected tests 29 passed. Renode comprises seven existing strict guards, 19 new sequence tests, and three MRAM/HAL/ROM-state regressions. New sequence tests cover stage 1–10 prefixes, six wrong-order types, two partial-access types, and option OFF. Individual guest readbacks, final register value/access counts/stage count, and whether completion writes occurred after stop were checked.

All six LP/HP conditions across two stock versions and Faceclaw completed all ten stages. Only the new option was added to existing zero Info1, virtual revision 0x23, power, HAL, and MRAM conditions. Each recorded 13 VRCTRL reads/writes, final value 0xfe1ef, then stopped at the next four-byte read:

| Input | Mode | Next address | PC |
| --- | --- | --- | --- |
| Stock 2.3.0.24 | LP, HP | 0x40020378 | 0x4896cc |
| Stock 2.4.0.24 | LP, HP | 0x40020378 | 0x4955b4 |
| Faceclaw 38 | LP, HP | 0x40020378 | 0x4896cc |

The address is SIMOBUCK15. Both engines matched raw main hash, next address, width, PC, stage count, final value, and VRCTRL access counts. The new named scenario's actual CLI was also run for stock 2.4 LP. With the option off, both executors retained the existing VRCTRL=0x2e000 request-rejection boundary. There were no memory protection violations or unverified Renode messages. boot_verified, hardware_validated, and installable remain false.

Tests are preserved outside Git in `buck-override-unittest-01/` and `renode-buck-override-verification-01/`, actual runs in `renode-buck-override-*-*-01/`, and comparison in `unicorn-renode-buck-override-comparison-01/comparison.json`.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/firmware_runner.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  --scenario startup-zero-info1-rev-23-buck-override-hypothesis \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-buck-override.json"
```

In Renode, add `--buck-override-storage` to the [MRAM control execution conditions](../cpu-memory/mram-auto-wakeup-control.md).

## Next boundary

Public HAL configures SIMOBUCK15 trim latch, compensation, and buck enable after override initialization. Execution in this report stopped at the first SIMOBUCK15 read. The subsequent [start-request storage test](buck-start-request-storage.md) connected control storage, and actual main stopped at an LDOREG1 correction write before enable. Full boot, firmware display, web installation, and real-device recovery verification remain incomplete. Actual glasses were not accessed.
