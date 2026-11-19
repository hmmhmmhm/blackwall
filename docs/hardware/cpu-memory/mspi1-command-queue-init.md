# Disabled MSPI1 Command-Queue Initialization

Original main from stock 2.4/2.3 and Faceclaw performed one CQ read/six writes, then stopped at DEV0XIP `40061090` write `5ED`. The existing guard blocked the request because it includes bit 0 XIPEN. This is not command-queue execution, memory fetch, XIP, MSPI transfer, or display success.

## Contract and implementation

Additionally preserved `am_hal_cmdq.c/h` from pinned HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` and compared SHA-256/Git blobs with the pinned tree. Files are in private `simulator/mspi1-cq-research-01`. MSPI `mspi_cq_init()` calls the common cmdq initializer to configure index 0, pause mask, buffer address, and priority/disabled configuration.

Shared HAL use by IOM and MSPI alone is not a reason to copy the current IOM engine. MSPI has a separate layout including CQSTAT paused bit 3 and CQFLAGS CQIDX bit 14/STOP bit 15. This model does not implement full hardware flags, execution, or pause semantics.

Added opt-in `commandQueueInit` to `renode-mspi1-config.cs`. Default is false, retaining the prior 25-register configuration contract and CQ blocking.

- CQCFG stores only priority bit 1. CQEN, poweroff, autoclear, and pause-op requests are atomically rejected.
- CQADDR checks word alignment without fetching. CQPAUSE and eight-bit current/end indices are stored.
- CQSETCLEAR applies set/clear/toggle to eight software flags. It follows documented set-over-clear precedence and rejects toggle conflicts whose meaning is unconfirmed. Alias reads are unsupported.
- CQSTAT is 0 in the reset/disabled profile where execution has never been allowed; writes are blocked. Entire CQFLAGS guest reads/writes are blocked because hardware inputs are unknown. Host diagnostic CQFLAGS contains software flags only.
- If power is not ready, access is blocked before counters/values change. Fixture owner reset initializes CQ state too. IRQ, PIO, DMA, and XIP were not added here.

## Verification

- unit01: failed on unimplemented constructor argument. unit02: 33 checks passed using local ready mock.
- main01: three originals, unselected control, and stuck-off, five conditions completed. Active three configured CQCFG=2, pause=`4000`, indices 0/0, software flags `80`, and aligned SRAM CQADDR. No actual engine start occurred.
- The next request for the three active cases was DEV0XIP write `5ED`: stock 2.4 PC `4E7EC0`, stock 2.3/CFW `4DAAEC`.
- Unselected retained the prior CQCURIDX write-0 boundary. Stuck-off was blocked at the previous first DEV0XIP read, with zero CQ reads/writes and initial values preserved. Do not describe a model block as the original's normal fallback.
- `mspi1-cq-init-verification-01`: 88 audit checks of eight public CQ metadata items, new HAL pins, original bytes, full model, board/runtime/fill, default/stuck, and XIP guard.
- `mspi1-cq-init-config-regression-01`: reverified 67 existing config-25 unit checks in the current model's default profile. Full boot, display, and physical transfer remained incomplete.

Next investigate the actual XIP request's peer, address window, and memory provenance. Do not pass it by simply storing enable or synthesizing unverified flash data. G1/G2 protocol references are auxiliary and do not replace original binary paths and model evidence.

Follow-up: the [NOR/XIP contract](mspi1-xip-contract.md) confirmed the NOR caller, read-only 32 MiB request at `80000000`, and original byte ABI. Full backing remains unknown and the guard was retained.
