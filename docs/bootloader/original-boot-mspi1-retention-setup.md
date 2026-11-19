# Connecting the MSPI1 shutdown callback during original boot

Status: bw534 in progress. Model shutdown conditions are not relaxed.

The original requested MSPI1 power-off with shared request 8400→400 (XOR 8000), retaining UART1 request 400. Pure-getter post-stop observation showed all 1163 transfers complete, PIO busy/recovery=false, RX/TX FIFO 0, CQ enable bit 0=0, DMA enable 0, and XIP violations 0. The MSPI1 controller itself was eligible for shutdown.

`CanPowerDown` was not called during observation because it can execute PIO.SyncTime. Only Values/CqValues and pure getters were read. Post-observation registers and instruction count matched before export, and previous bw533 registers/instruction count/boot globals also matched exactly. Observation is not treated as boot progress or state change.

The existing successful main runtime calls `Mspi1Config.AttachRetentionPower(Mspi1Power)` before startup, but the minimal boot runtime omitted that connection. Thus power.CanShutdown had no callback. MSPI1 retains the existing explicit external-NOR-retained functional profile; only the same one-line pre-start connection is restored. CPU phase/branch/return and runtime device state are not forced, and all existing FIFO/CQ/DMA/XIP shutdown conditions remain.

Pre-CPU-start calls in existing main were also compared. Memory policy/system control Attach calls already exist; the others are UART IRQ observation hooks. The functional connection restored here is the MSPI1 retention callback. Main observation hooks at addresses different from original boot are not added unnecessarily.

## Verification material

- `private:simulator/original-boot-mspi1-off-state-native-bw534-01/exports/mspi1-off-state.json`: pure state at actual stop.
- `private:simulator/boot-mspi1-setup-proof-bw534-01/setup-proof.json`: exact before/after observation comparison, existing main connection/boot omission, and SHAs.
- `private:simulator/boot-mspi1-retention-regression-bw534-01/report.json`: 39 existing --xip-restore checks passed, including rejection during FIFO/recovery and external NOR latch preservation/controller reset.
- `private:simulator/original-boot-mspi1-retention-native-bw534-01/plan.json`: exact model/board/probe, with one callback line changed before execution.

External NOR supply retention is an existing digital assumption. It does not establish that supply remains on in actual glasses or that installation/recovery is safe.

## Original execution and next investigation

After callback restoration, 41,312,219 original instructions/4.1312219 virtual seconds executed. Thirty-six MSPI1 controller power-downs and 1317 completed PIO transfers were confirmed; guard/code/system protection and CFSR/HFSR were all 0. The MSPI1 shutdown request passed, but execution ended at original delay entry 41d20a at the host 120-second limit. It did not complete ten virtual seconds or reach main.

Whether repeated power cycles are normal initialization/scan or retries remains undetermined. Next collect UART TX log, stop-time stack, and NOR/scan state through pure getters and compare original callers. Do not simply keep extending timeout. Authoritative record: `private:simulator/original-boot-mspi1-retention-native-bw534-01/frontier-proof.json`.

Two identical boot dumps totaling 299546 bytes from state diagnosis and candidate execution, and synthetic spin.bin of 10 bytes, were checked and removed. Owned Docker removal for three runs was confirmed. Key analysis, execution source, pinned model, logs, original SHA, reproduction commands, and seed hex remain.
