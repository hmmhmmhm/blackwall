# Memory Power State and Single ROM-Disable Model

Status: an assumption for offline execution of actual pinned main. Actual device power state, calibration, and boot were not verified.

In the [pinned PWRCTRL definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/pwrctrl_regs.html), `0x40021014` is MEMPWREN and `0x40021018` is MEMPWRSTATUS. Status and enable bit layouts differ, and real transitions may have delay. Status is not returned as the enable value unchanged.

The stock 2.4 path at `0x494964` checks whether status & `0x48` equals `0x8`. This corresponds to the branch that adds NVM1 when only NVM0 is on. Do not treat that branch as confirmation of actual power state.

## Fixed ON state

Select `--memory-domains-on` with the power-mode model. The virtual initial state is:

- MEMPWREN=`0x3f`: all TCM, NVM0, NVM1, and ROM ON.
- MEMPWRSTATUS=`0xcf`: corresponding status, cache OFF.
- Separate power/retention for ROM contents and System SRAM is unimplemented.

Only aligned four-byte reads and rewriting the current enable value are allowed. Partial-width access, status writes, and other enable values stop execution. Values are explicit assumptions, not readings from the user's actual device. There is no actual latency or voltage/isolation sequence.

Executed stock 2.3, 2.4, and Faceclaw 38 with `startup-zero-info1-rev-23-memory-on-hypothesis`. All stopped immediately before writing enable=`0x1f`. PCs were 2.3/Faceclaw `0x488ab0` and 2.4 `0x494998`; final r0=`0x1f`, r8=`0x40021014` confirmed the requested value. MEMPWRSTATUS was read three times and MEMPWREN once. Results are outside Git in `Blackwall/simulator/memory-power-on-01/`.

## Optional ROM-disable transition

This request changes `0x3f` → `0x1f`, clearing only enable's ROM bit. Select `--rom-powerdown-model` with the ON fixture above; it allows only this single transition:

| Item | Before | After |
| --- | --- | --- |
| MEMPWREN | `0x3f` | `0x1f` |
| MEMPWRSTATUS | `0xcf` | `0x4f` |
| ROM-disable events | 0 | 1 |

Status changes immediately under a **zero-delay assumption**. Not making status polling wait does not reproduce actual power response time. ROM reactivation, TCM/NVM power changes, other registers, and status writes are unsupported. ROM is not newly mapped as an executable region. If a power transition is rejected, the report also records the requested value in `access.value`.

Executed `startup-zero-info1-rev-23-rom-disable-hypothesis` once for each of three images. Each recorded one ROM disable, one identical-value enable write, five enable reads, and ten status reads before stopping on the next `0x4002101c` read. PCs were 2.3/Faceclaw `0x488b8e` and 2.4 `0x494a76`. Results are outside Git in `Blackwall/simulator/rom-disable-01/`. Report fields `hardware_verified`, `boot_verified`, and `installable` are all false.

Passed 58 runner and three scenario tests, including initial readback, single transition, rejection of ROM reactivation and NVM power changes, and rejection of status writes/partial reads. The two options were not automatically added to existing scenarios, preserving existing stop boundaries.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" tools/firmware_runner.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  --scenario startup-zero-info1-rev-23-rom-disable-hypothesis \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-rom-disable.json"
```

Next analyze MEMRETCFG reads and memory-retention configuration in deep sleep. Full boot, RTOS, display transport, and actual installation/recovery compatibility remain incomplete.

## Memory-retention configuration storage model

The subsequent `--memory-retention-storage` stores only bits 0/1 of MEMRETCFG `0x4002101c`. In public register documentation bit 0 configures TCM power-down in deep sleep and bit 1 configures NVM power-down. Documented initial value 2 is used as a virtual fixture, not treated as actual device state. Only aligned four-byte reads and writes of values 0–3 are supported. Reserved bits and partial-width access stop execution.

This option does not implement sleep entry, TCM data loss/retention, or wake-up. A test reaching WFI after setting the TCM power-down bit still stopped at `unsupported-sleep-boundary`. Do not report stored configuration as verified retention behavior. Reports record `sleep_and_retention=not-modeled`.

Executed three images with `startup-zero-info1-rev-23-retention-storage-hypothesis`. Each recorded two MEMRETCFG reads, two writes, final value 2, and stopped at the next shared-SRAM power-status read at `0x40021028`. PCs were 2.3/Faceclaw `0x488c76`, 2.4 `0x494b5e`. Results are outside Git in `Blackwall/simulator/memory-retention-storage-01/`. Passed 61 runner and three scenario tests.

Next analyze shared SRAM power enable/status. Actual memory power transitions, sleep, boot, display, and web-installation compatibility remain unverified.

## Shared SRAM ON state and retention configuration

Compared public PWRCTRL definitions with the existing System SRAM range. The low three bits of SSRAMPWREN=`0x40021024` and SSRAMPWRST=`0x40021028` correspond to three 1 MiB groups. `--shared-sram-on` is a virtual state providing 7 for both enable and status. It requires the existing 3 MiB System SRAM mapping and power-mode model; power changes, status writes, and partial-width access stop execution. Only rewriting enable 7 is allowed. Actual SRAM power and power-transition latency are not modeled.

`--shared-sram-retention-storage` is separate. At SSRAMRETCFG=`0x4002102c`, it stores only PWDSLP bits 2:0, MCU bits 5:3, GFX bits 11:9, and DISP bits 14:12. Write mask is `0x7e3f`; reserved bits are rejected. Initial value `0x7e38` is a synthetic fixture using public reset bits, not user-device state. Effects of sleep, bank data loss/retention, wake-up, and GFX/DISP state changes are unimplemented.

Added two scenarios:

- `startup-zero-info1-rev-23-shared-sram-on-hypothesis`: adds shared SRAM ON state only.
- `startup-zero-info1-rev-23-shared-sram-retention-hypothesis`: also adds retention configuration storage.

The first scenario stopped on stock 2.4 at the next `0x4002102c` read. The second ran once each on stock 2.3, 2.4, and Faceclaw 38. All recorded one shared SRAM status read, zero power-enable writes, four retention reads and writes each, and final value 0 before stopping on `0x40021040` read. PCs were 2.3/Faceclaw `0x488d5a`, 2.4 `0x494c42`.

All four results are outside Git in `Blackwall/simulator/shared-sram-01/`. Passed 64 runner and three scenario tests. Hardware verification, normal boot, display transport, and actual installation/recovery compatibility remain incomplete.

## Shared SRAM override configuration storage

After `0x494c42`, the actual stock 2.4 path for MMSOVERRIDE `0x40021040` clears GFX-related retention field `0x3800`, then DISP-related field `0x700`. `--shared-sram-override-storage` stores only observed `0x1b0c`, `0x30c`, and `0xc`, starting from synthetic `0x1b0c` using documented reset bits. Only aligned four-byte access is supported; MCUL control-bit changes, reserved-bit changes, and other values stop execution. Actual GFX/DISP power and SRAM retention effects are not modeled.

Executed `startup-zero-info1-rev-23-shared-sram-override-hypothesis` once for each of three images. All read and wrote this register twice, recorded final value `0xc`, then stopped at the next `0x40004044` read. PCs were 2.3/Faceclaw `0x4893ec`, 2.4 `0x4952d4`. Results are outside Git in `Blackwall/simulator/shared-sram-override-01/`. Passed 66 runner and three scenario tests. Normal boot and display transport remain incomplete.
