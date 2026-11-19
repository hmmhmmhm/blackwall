# Local NOR Sector Erase and the Original Formatter

## Supported scope

Added instruction 20/CTRL `00e1`, which stopped in [bounded reads](mspi1-bounded-array-read.md), to local RAM-backed NOR. Existing `BlackwallNorReadWindow` creates a byte array from an initial profile and returns copies for reads. `allowSectorErase` defaults to false; even when allowed, the **entire 4 KiB sector** must lie within the declared range. Any address within a sector selects the same aligned sector and does not erase other sectors or adjacent NVdb.

PIO also requires explicit `sectorEraseMicroseconds`. Default 0 means unsupported/unknown, not success. Only 1–1,000,000 µs is accepted, requiring bounded backing and dynamic WEL. A known time with read-only backing still rejects erase. Unit tests selected 100 µs; native comparison selected 1,000 µs. Both are **test assumptions, not physical device measurements**.

This implementation of command 20 requires CFG `3010061`, CTRL1=0, supported SDR control, EN4B required for the legacy opcode, WEL=1, and known unprotected status seed 0/40. It does not implement all BP/security/suspend/reset-during-erase behavior. Other protection states and unimplemented commands are not treated as successful.

## Two-stage completion and content preservation

Device erase begins at the controller's existing 10 µs wire completion. WIP=1/WEL=1 from that point, but byte contents have not yet changed. Only when a separate NOR timer completes is the selected sector changed to FF and WIP/WEL cleared. Device completion itself does not generate a controller IRQ. While busy, only supported RDSR may be accepted, returning status 43; other commands are rejected.

Under retained external-supply conditions, the NOR timer continues even if the controller is turned off. Controller-only initialization does not cancel device work, contents, or cumulative history. Completed contents remain after owner and backing Reset. Conversely, **emulator scenario Reset during incomplete erase cancels the timer and preserves previous contents**. This does not reproduce partial erase results under actual power loss or reset. Actual power-loss damage scope is unverified. Also distinguish starting a new emulator process from initial profile and resetting the same object.

Compared WEL/WIP, sector selection, and address-mode rules on manufacturer PDF pages 25/67 and pinned SVD in 19 conditions. Source/frame material is outside Git at `simulator/mspi1-erase-contract-01`. Actual pin routing, silicon timing, and existing logical transport assumptions remain unconfirmed.

## Original main execution results

| Condition | Result | Next strict request |
| --- | --- | --- |
| Stock 2.4 / 1000 µs | One erase completed, guest status 43 → 40, then separate WREN | PC `4e8a46`, instruction 02/CTRL `1000e1`, 16-byte program |
| Stock 2.3 / 1000 µs | Same | PC `4db672`, same request |
| Faceclaw 38 / 1000 µs | Same | PC `4db672`, same request |
| Stock 2.4 / time unselected | Zero erases | Previous 20/CTRL `00e1` |
| Stock 2.4 / read-only backing | Zero erases | Previous 20/CTRL `00e1` |
| Stock 2.4 / no-completion fault | WIP 1 retained, zero erase completions, original poll timed out three times | Instruction 6c/address `01fc1000` read |

In three normal paths, original code actually observed busy status 43 and 40 after completion and exited polling. It then prepared page program; a third WREN completed, making final WEL=1/status 42. **Distinguish erase completion clearing WEL from the next command setting WEL again.** Program was not yet started or completed.

The incomplete condition ran only on stock 2.4. Observed 3,600 `status-result=1` and three `status-poll-return=1` events. Nevertheless, the caller attempted to read the next sector while NOR was still busy; this read was blocked. Therefore timeout handling, safe fallback, or recovery was not established. Do not generalize this result to all other firmware or actual device behavior.

Main bytes matched pinned originals; guest branches, returns, and delays were not forced. Normal paths preserved the prior 368 events and finished with 396, zero drops. Existing synthetic memory/identity/power assumptions and main-reset starting scope remain. This is not full ROM/bootloader boot proof.

## Tests and evidence

Unit tests checked that nonuniform initial data becomes FF across all 4,096 bytes only on completion and neighboring sectors remain unchanged. They covered WEL/WIP, unaligned sector addresses, out-of-range, protected/read-only/unsupported profiles, unset EN4B, wire-clock abort, completion while controller off, stale-event prevention after pending Reset, and completed-content preservation on Reset. Unit/regression total: 238 conditions.

Final artifacts outside Git:

- `simulator/mspi1-erase-unit-02`: 26 conditions; `stuck-unit-01` 20, `disabled-unit-01` 8, `readonly-unit-01` 8, `protected-unit-01` 8, `reset-unit-02` 20, `abort-unit-01` 12, `address-mode-unit-01` 7. Common prefix is `mspi1-erase-`.
- Array 46, status 44, and XIP/off 39 regressions: `mspi1-erase-array-regression-01`, `status-regression-01`, and `xip-regression-01` respectively.
- `simulator/mspi1-erase-main-01`: six conditions covering three normal originals, default, read-only, and `stock24-stuck-compact`. Initial `stock24-stuck` was preserved after the startup failure below.
- `simulator/mspi1-erase-verification-01/report.json`: 137 checks comparing current model, original bytes, input SHA, logs/reports, prefix, guest busy → idle/timeout, and program blocking.

The first native fault attempt ended **before CPU execution** because I specified observer capacity 16,384 although its maximum is 4,096. Do not treat it as a firmware timeout result. Preserved the failure log and removed duplicate status-byte hooks only in the fault case, keeping all result/poll events within 4,096. Final count was 3,974 with zero drops; prior-prefix comparison used an explicit projection removing the same labels and renumbering sequence. Other observation points and peripheral models were unchanged. Initial exception reporting's JSON import order was also fixed.

A read-only review by an agent inheriting the parent model suggested wire-abort and EN4B negative tests, which were incorporated. No Astra, other model family, or full conversation audit was run.

## Next steps and limits

Later [page program verification](mspi1-page-program.md) pursued the program/readback work below. The following describes the boundary at the end of this erase stage.

Next establish the TX FIFO, page boundary, 1 → 0 bit changes, WEL/WIP, and completion contract for instruction 02/16-byte page program. Verify consistent actual RAM-backed content changes instead of supplying only success values. Normal KVDB creation and later readback were not yet verified.

All erases occurred only in emulator RAM. Original firmware files were unchanged and actual NOR/MRAM was not written. There was no glasses connection, scan, RAM payload, OTA, or flash. Normal DB initialization, full boot, integrated display, and physical installation/recovery remained incomplete; product criteria stayed 13/29, 44.8%.
