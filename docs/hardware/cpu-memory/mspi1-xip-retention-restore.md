# MSPI1 XIP Retention Configuration Restore

## Cause and source evidence

After [controller power-off](mspi1-power-off-model.md), original main restores AXI, DEV0CFG, DDR, and CFG1 in order, then writes the complete saved DEV0XIP word at once. `0xed` includes XIP enable and instruction, address, turnaround, ACK, and other fields. The previous adapter treated a change to enable and other fields together only as a live timing/mode change while XIP was already enabled, so it rejected this initial restore.

`tools/inspect_mspi1_xip_restore_contract.py` compared pinned SVD/header and HAL SHA, three original mains, and previous native captures. The 26 checks in `simulator/mspi1-xip-restore-contract-02/report.json` outside Git confirmed DEV0XIP offset 90/reset 0/mask 03FFFFFD, mixed values 0/1/3/5/7/9/11, ACK values 0/2/3, and original `LDR state+874 → STR module+90`. Initial contract-01 failed a check dependent on whitespace in HAL text; it was not a meaningful source change. The whitespace-normalized 02 is the final evidence.

## Bounded model

`xipRestoreStorage` is opt-in and defaults to false. It prepares a restore exception only in a successful retained-controller off callback, then applies it to the first enable write while the XIP guard is disabled. This path checks documented mixed/ACK enums, the existing register mask, AXI19, power-on, and supported clock conditions. A rejected request does not change enable, registers, or the exception. Success consumes the exception and increments `XipRestoreWrites`. Full Reset clears both the exception and counter.

This is a restriction on **an atomic restore write after power-off**, not a one-time permission for the entire existing disable → configure → enable path. XIP mapping enable changes only guard state; it supplies no flash backing, data, execute, or DMA functionality. External NOR power retention and the digital off response remain explicit mock assumptions, not verification of actual power, lanes, or timing.

## Execution results

| Condition | Next boundary reached | Observation |
| --- | --- | --- |
| Stock 2.4 / restore opt-in | PC `0x4e8a46`, CTRL `0x10441` write | One XIP restore; reached end of saved-state restoration |
| Stock 2.3 / restore opt-in | PC `0x4db672`, same CTRL write | Same |
| Faceclaw 38 / restore opt-in | PC `0x4db672`, same CTRL write | Same |
| Stock 2.4 / default | Previous PC `0x4e9054`, XIP `0xed` write | Exception not selected; zero restores |
| Stock 2.4 / stuck-on | Previous PC `0x494d78`, enable `0x8400` write | Zero actual offs and zero restores |

On all three successful opt-in paths, R2 was ED at the observation point following original `STR DEV0XIP`. Execution also reached the point after restoring the remaining saved MSPI registers and clearing the valid flag where it branches to the success epilogue. Observation points are `0x4e9058` and `0x4e9182` for 2.4, and those addresses minus `0xd3d4` for 2.3/CFW. R0=0 at the latter is the value at this **state-restoration endpoint**, not proof of a complete successful boot.

All previous 353 observation events were preserved. The three successful paths had 355 events with two added observation points and zero drops. Default and stuck-on endpoints also remained unchanged. Each main matched the original bytes in the pinned bundle; no forced branches, injected returns, or skipped original delays were added. Existing synthetic memory, identity, and power assumptions still apply. NOR four-byte mode and status were preserved.

Verification assets are retained outside Git:

- `simulator/mspi1-xip-restore-main-02/`: input manifests, Renode logs, and reports for five original conditions. main-01 is the stock24 result before adding the endpoint observation.
- `simulator/mspi1-xip-restore-unit-02`: 39 restore-selected conditions. red-01 records the initial unsupported constructor API failure; unit-01 passed before adding the post-reset authorization-revocation check.
- `simulator/mspi1-xip-restore-default-unit-02`: 37 default conditions. Checks that an atomic restore exception cannot be used without a new off even after restoring correct power, clock, and AXI.
- `simulator/mspi1-xip-restore-mixed-regression-01` and `power-regression-01`: regressions for 63 existing XIP and 26 controller-off conditions. Total unit and regression coverage is 165 conditions.
- `simulator/mspi1-xip-restore-verification-01/report.json`: 92 checks comparing logs/reports, current model, original bytes, derived SHA, event prefix, restore points, and default/failure boundaries.

A read-only review by an agent inheriting the parent model reported no additional material production errors. Following its warning that a zero counter after full Reset alone does not prove the exception vanished, a behavioral test verified rejection of an atomic ED write without a new off and passed again. Astra and other model-family review were not used.

## Next boundary

Subsequent [continuous status logic modeling](mspi1-continuous-status-read.md) investigated and supported this status boundary, advancing to an array-read request. The following records the state at completion of this XIP work.

The next unsupported request was controller CTRL `0x10441`. The final instruction observed was 05 and DEV0CFG was `0x01010861`, unlike the existing fixed RDSR profile. Compare the exact original command, configuration meaning, and sampling conditions before extending the required PIO contract. This frame had not yet been processed successfully.

Full boot, integrated display, and physical recovery remained incomplete. Overall completion criteria remained 13/29, 44.8%. No BLE connection or scan, glasses RAM payload, flash, OTA, or MRAM write was performed.
