# Order-Limited Storage of SIMOBUCK Start Requests

Status: storage of three controls—trim latch, compensation, and enable request—connected to two executors. Actual power, trim latch, compensation circuit, and ready response are not implemented. Actual main currently stops on a separate correction write after two stages and has not reached enable.

## Sources and initial conditions

Public HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` header, MCUCTRL/PWRCTRL HTML, and `am_hal_pwrctrl.c` were used. Reset words below were assembled from original SHA256 and field masks, and three offsets checked with actual clang M55 `_Static_assert(offsetof(...))`. After confirming exact main hashes for stock 2.3/2.4/Faceclaw, literals for the three addresses and OR values were compared.

| Order | Control / address | Virtual initial value | Requested stored value |
| --- | --- | --- | --- |
| 1 | MCUCTRL SIMOBUCK15 / 0x40020378 | 0 | 0x80000000, TRIMLATCHOVER |
| 2 | MCUCTRL SIMOBUCK0 / 0x4002033c | 0 | 0xf, four rail compensation enable bits |
| 3 | PWRCTRL VRCTRL / 0x40021100 | 0 | 1, SIMOBUCKEN |

These reset words are virtual inputs from public material, not actual device manufacturing calibration or state after bootloader execution. SIMOBUCK15 rail-enable trim also has public reset 0 and is not treated as a valid running calibration value. Validity of actual rails, voltage, and transition time is unknown.

Public HAL and binary contain a separate SPOT handler call between stages 2 and 3. The storage model does not replace this function with a stub. Actual main executes the code, and unsupported correction writes stop as before. Analysis and compiler logs are outside Git in `Blackwall/simulator/buck-start-source-analysis-01/`.

## Model and readiness blocking

Explicitly select `--buck-start-storage`; default is OFF. Unicorn requires ordered override storage and power mode. Renode also requires explicitly specifying ordered override. The MCUCTRL and PWRCTRL pages share one progress state.

All writes require completion of the preceding ten VRCTRL override stages. Only the above addresses, values, order, and aligned four-byte accesses are allowed. Early compensation/enable, trim-bit changes, unsupported disable, and partial accesses are rejected. Stage 3 completion records only `enable_requested=true`; it does not mean power-ready.

After enable request, a PWRCTRL VRSTATUS (0x40021108) read stops. It is blocked before the existing HAL reset fixture's 0 can be used as readiness. Even handling an enable request in a synthetic fixture does not create an actual power-ready response. This guard was independently tested; actual main has not yet reached that read.

## Verification scope

The full request sequence was first confirmed to fail on the existing implementation. Final Unicorn runner/profile tests 94 and Renode selected tests 23 passed. Renode comprises seven strict guards, 13 new request-model tests, and three existing override/MRAM/HAL regressions. New-model tests cover three prefixes, six invalid request types, readiness blocking, two partial-access types, and option OFF. In particular, readiness testing checked that VRSTATUS read count did not increase with the HAL reset fixture actually enabled.

Distinguish these results:

- Independent tests verified storage of three requests and readiness blocking after enable.
- Actual main stopped at the SPOT handler's LDOREG1 write after storing two requests.

## Actual main execution and next boundary

The new option was added to existing zero Info1, virtual revision 0x23, power, HAL, MRAM, and override conditions. In all six LP/HP cases for two stock versions and Faceclaw, SIMOBUCK15=0x80000000 and SIMOBUCK0=0xf each recorded one read/write. PWRCTRL VRCTRL had zero reads/writes and enable_requested=false. The next unsupported access was a four-byte write:

| Input | Mode | Address / requested value | PC |
| --- | --- | --- | --- |
| Stock 2.3.0.24 | LP, HP | 0x40020080 / 0x6d3cd | 0x5bad34 |
| Stock 2.4.0.24 | LP, HP | 0x40020080 / 0x6d3cd | 0x5c22dc |
| Faceclaw 38 | LP, HP | 0x40020080 / 0x6d3cd | 0x5bad34 |

The address is MCUCTRL LDOREG1. Read-only public reset value 0x6d3d4 was preserved and write count was 0. This report did not authorize or store the requested value. Subsequent [core LDO reduction test](coreldo-saturated-reduction.md) confirmed the original function's calculation and connected a limited write policy. Validity of actual manufacturing calibration and voltage remains unconfirmed.

Both engines matched raw main hash, stop address, width, PC, requested value, and three control-register states/access counts in all six cases. The actual CLI for the new named scenario was also run for stock 2.4 LP. With the option off, both retained the previous SIMOBUCK15 read boundary. No memory protection violations or unverified Renode messages occurred. boot_verified, hardware_validated, and installable remain false.

Unit logs are in `buck-start-unittest-01/`, Renode tests in `renode-buck-start-verification-01/`, actual runs in `renode-buck-start-*-*-01/`, and comparison in `unicorn-renode-buck-start-comparison-01/comparison.json`.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/firmware_runner.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  --scenario startup-zero-info1-rev-23-buck-start-hypothesis \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-buck-start.json"
```

In Renode, add `--buck-start-storage` to the [override execution conditions](buck-ldo-override-sequence.md). Full boot, firmware display, web installation, and real-device recovery verification remain incomplete; actual glasses were not accessed.
