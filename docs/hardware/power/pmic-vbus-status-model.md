# Explicit VBUS Status and Natural M55 Consumption

bw-0302. The [original status-consumption contract](pmic-vbus-status-contract.md) was connected to an optional PMIC snapshot. No actual device, case, or power was accessed.

## Model scope

A final optional `vbusStatusProfile` argument was added to the PMIC root and timed wrapper. `test-vbus-absent` returns 0 on `0x0207` reads; `test-vbus-present` returns 1. When omitted, status is unknown and the pointer request remains blocked as before. Arbitrary byte values and automatic detection are not allowed.

Only one-byte reads after STOP are supported. All 256 status-write values, bursts, invalid lengths, duplicate pending transactions, and neighboring unsupported registers are rejected. Read count increases only for accepted reads. Reset clears the count and preserves the explicit fixture selection. Existing VBUS current/suspend configuration and apply requests, charger, and watchdog behavior are unchanged.

This is a digital status-branch experiment. It does not also generate VBUS voltage, ADC samples, charging state, rails, VBUSOUT, or interrupts. In particular, the present profile is not a complete power model physically consistent with existing ADC test samples.

## Natural original execution

Renode M55 ran from reset without modifying original main bytes, branches, or return registers. Inputs were derived after verifying the pinned image, full SRAM, and audit provenance from an earlier advertising run. VBUS reads traversed original IOM7, backend, wrapper, and consumer paths through the new PMIC model.

| Run | VBUS read | Original internal status byte | Next stop PC |
| --- | --- | --- | --- |
| Stock 2.4 / absent | Once, 0 | 0 | `0x494d78` |
| Stock 2.4 / present | Once, 1 | 1 | `0x494d78` |
| Stock 2.3 / absent | Once, 0 | 0 | `0x488e90` |
| Faceclaw38 / absent | Once, 0 | 0 | `0x488e90` |

Original analysis located the status byte at stock 2.4 `0x20076551`, older/CFW `0x20076f19`. Final SRAM values matched each selection. Both 2.4 cases had 72,932,150 executed instructions but different status inputs and stored values. Equal instruction counts alone do not make execution results identical.

All four candidates strictly stopped at the next **`PWRCTRL.DEVPWREN(0x40021004) = 0x4e00`** write. Original `str r1, [r0]` and actual register arguments were compared. Original stock 2.4 context retains peripheral enum 16 and enable/status mask `0x4000`. The next stage investigates the power owner and reactivation lifecycle; this request has not yet been accepted.

Existing advertising 59 commands/60 responses remained. The default unknown control had zero VBUS reads and exactly matched existing CPU, instruction count, all events, and unsupported PMIC boundary. Present combinations for stock 2.3/CFW were not run here.

## Verification and preserved failures

- After preserving a red for the absent new constructor, 625 snapshot checks passed; the same 625 were reverified on frozen sources.
- Existing VBUS configuration 252, charger status 118, and watchdog/timer 240 regression checks passed.
- Five natural native runs and five saved audits. The first four candidates failed because expected bounded idle differed from the actual strict power boundary; original reports were preserved. Saved audits used a separate contract without rerunning CPU and overwriting results.
- Saved analysis repeated with 64 frozen Python dependencies yielded byte-identical report and inspector files. Four existing EM9305, IOM, key DB, and OTA marker model hashes were unchanged.

Evidence: `private:simulator/vbus-status-peer-verification-01/manifest.json`. Preparation/check tools are `prepare_vbus_status_candidate.py`, `inspect_vbus_status_profiles.py`, and `verify_pmic_vbus_status.py`. Proprietary originals, RAM, and execution logs remain outside Git.

This result does not verify full boot, app loop, integrated display, physical VBUS, or real-device installation. Web installer, recovery boot, and installation CFW were unchanged. Overall scope v2 remains 13/29=44.8%. Next, confirm the exact source contract for the power request and continue connecting the natural app/display path.
