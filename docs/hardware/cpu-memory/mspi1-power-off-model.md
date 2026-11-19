# MSPI1 Controller Power-Off and External NOR Retention

## Implementation scope

Following the [original power-off contract](mspi1-power-off-contract.md), added an explicit mock condition in which **external NOR power remains on while only the MCU MSPI1 controller domain is turned off**. Neither that power relationship nor actual silicon register loss has been verified on hardware. A passing mock is not installation/recovery verification or authorization for hardware writes.

Opt in with `BlackwallMspi1ConfigStorage.AttachRetentionPower()` and explicitly set the existing power owner's offProfile to success 0 or stuck-on 1. The unknown default remains blocked. On connection, the PIO's actual PowerOwner is checked by object identity. Another object with the same mask, duplicate attachment, an already-started owner, and unknown off responses are rejected.

Shutdown is allowed only when PIO is not busy, there is no unconsumed RX or NOR recovery, and CQ/DMA are disabled. It is rejected if the XIP guard has actually been accessed. On this original path XIP is configured as enabled, but no aperture access occurs, so the model has no active memory transaction. Do not generalize this condition as proof of an actual hardware flush.

When a successful off status is observed, internal config/CQ are initialized to existing source-reset values and CTRL/FIFO, IRQ enable/status/line, and XIP guard enable are cleared. NOR WEL, four-byte mode, reset-enable, seed, completion history, and guest read/write counters are retained. Full simulator Reset clears NOR state and diagnostic counters as before. An off request alone or a stuck-on response does not reset the controller.

## Verification results

Final mock unit tests checked 106 conditions: normal 26, stuck-on 14, unknown 4, owner identity 6, and existing CQ 33/WRDI 23 regressions. Unit tests use a short spinning ARM fixture and host-driven stimuli; distinguish them from original main execution below.

| Original execution condition | Power function return | Controller off count | Next strict boundary |
| --- | ---: | ---: | --- |
| Stock 2.4 / off success | 0 | 1 | PC `0x4e9054`, write `0xed` to `0x40061090` |
| Stock 2.3 / off success | 0 | 1 | PC `0x4dbc80`, same XIP restoration write |
| Faceclaw 38 / off success | 0 | 1 | PC `0x4dbc80`, same XIP restoration write |
| Stock 2.4 / stuck-on | 4 | 0 | PC `0x494d78`, reactivation request `0x40021004 = 0x8400` |
| Stock 2.4 / unknown | Did not reach call return | 0 | Existing PC `0x494f3e`, off request `0x400` |

In all three success conditions original code requested power-on again after off. `power_cycles=1` counts completed off responses, not complete board power cycles or successful physical recovery. The final phase is on. NOR address mode and status were retained. The observed prior 352-event prefix was preserved; success and stuck-on added one return observation for 353 events, while unknown had 352. Event drops were 0. Original main bytes matched the pinned bundle and no forced branch or delay skip was added. Existing synthetic identity, memory, and power assumptions continue to apply.

**In stuck-on, the original receives error 4 but proceeds without checking it.** The current power state machine rejected the subsequent reactivation request. Actual device reactivation behavior is unknown; do not interpret this result as safe fallback or recovery.

Final artifacts outside Git:

- `simulator/mspi1-power-off-main-02/`: input hashes, native logs, and reports for three original success cases, stuck-on, and unknown.
- `simulator/mspi1-power-off-verification-01/report.json`: 84 checks comparing original bytes, derived input SHA, logs/reports, existing event prefix, next boundary, NOR state, and unit tests.
- Normal unit `mspi1-power-off-unit-03`, stuck/unknown units `*-unit-02`, owner unit `mspi1-power-off-owner-unit-01`, and CQ/WRDI regressions `*-regression-02`.

Initial failures were also preserved. `power-off-red-01` lacked the Attach API; `unit-01` failed because the fixture expected an incorrect config reset (the correct DEV0CFG reset is `0x20001`). `owner-red-01` was a CLR import failure, not evidence of functional failure; `owner-red-02` reproduced an actual foreign-owner acceptance defect that was then fixed. Initial main-01 predates the identity check; final assessment uses main-02.

Following the `requesting-code-review` skill, an agent inheriting the parent model conducted a read-only review. It identified an owner wiring defect, which was fixed; rereview reported no additional material defects. Astra, other model families, and full conversation audit were not used.

## Next work and limits

Subsequent XIP restoration implementation and new execution endpoints are recorded in [XIP retention restoration](mspi1-xip-retention-restore.md). The following describes the next boundary at the time this power-off work ended.

The next boundary is restoration of the saved DEV0XIP configuration. The current limited adapter rejects the original sequence that restores timing/mode fields together with the first XIP enable after reset. Investigate the exact original, HAL, and field contracts before adding the necessary restoration path. Do not simply allow all XIP configuration or backing memory.

Full boot, integrated display, actual BLE, and physical recovery remain incomplete. Product completion remains 13/29, 44.8%. There was no glasses connection, scan, RAM payload, flash, OTA, or MRAM write.
