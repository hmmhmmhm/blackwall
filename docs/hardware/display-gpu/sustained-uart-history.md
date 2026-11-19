# Sustained UART transmission and bounded observation history

bw498–500. Original ARM and physical devices are unchanged. This functional profile separates original main UART DMA transmission from host cumulative recording budget. It is not physical UART/DMA timing certification.

## Actual stop and cause

Private `sustained-uart-inspection-native-01/stock24` stopped 31.144718 seconds after screen on guard_high write `0x40039048`, width 4/value 0x0a. Original PC0x57f03c is `str r0,[r2,#0x48]` with r2=UART0 base 0x40039000. Do not interpret it as ordinary TX-byte transmission from address name or r0=10 alone.

Termination observation recorded UART0 power on/PowerBlocks0/Control0x319/baud923076, DMA idle and control/status/raw IRQ 0, target 0x2035cc60/count 21, cumulative TX 4088. Target+count is within SRAM. `CanDmaTransmit` condition `TxBytes.Count+count<=4096` becomes 4109 and rejects. This is a cumulative limit of the List storing historical transmission, not a single DMA length 4095 or physical FIFO. Unmeasured engine line-control/private targetSet/countSet conditions remain separately unknown; conclusion is limited to the cap being a definite rejection condition.

After correcting observer variable collision by function isolation, all execution_checks of this rerun passed and original subsequent exporter completed. Target/fault semantic checks failed. It is not counted as successful original 60 seconds. Container removal and resource observer exit were confirmed. Proof: `sustained-uart-frontier-proof-01/report.json`.

## Explicit bounded-prefix profile

`uart_tx_capture_model.py` optionally composes only one existing UART adapter component with SHA07f366fd…. Shared original `renode-strict-mmio.cs` was unchanged. `boundedTxCapture` defaults false.

When explicitly true for UART0, only first 4096 transmitted bytes are preserved, while each actual engine CharReceived accumulates total byte count, FNV1a64, discarded-record count, and truncation status. IRQ/completion retain actual engine/DMA path. Single DMA length 4095, full SRAM bounds, power, baud/line, DMA ready/active, and status/IRQ cleanup checks remain. Invalid transfers are not ACKed as success and original buffer/branches/tasks are unchanged.

`TxBytes` is not full history in this profile. Above 4096 it must be labeled prefix; full transmission is distinguished using cumulative count/hash and DMA material. FNV is a stream-comparison summary, not a substitute for cryptographic integrity. SHA256 is used for asset/source/capture integrity. DMA transfer list is preserved for this finite 60-second run; indefinite memory bounds are not certified.

## Execution verification

| Test | Result |
| --- | --- |
| Existing adapter / 4088+21 transfer | Expected rejection reproduced at `second21-emitted-past-history-budget` |
| New optional profile | 75 checks passed. Includes actual SRAM source bytes and completion/IRQ, 4096 prefix, 4109 cumulative/13 dropped, full stream hash, PIO, invalid, powerdown/reset |
| New component default false | 62 checks passed. Existing 4096 cumulative-budget rejection retained |
| Existing UART1 adapter/power/IRQ regression | 117 checks passed |
| Sustained observation/audit units | 11 checks passed, including rejection of overriding original runtime name |

The 254 device tests are transactions of actual Renode device classes, not original G2 ARM execution; they are not added to native successes. Inputs/models/logs/reports preserved in private `uart-tx-history-{red,green,disabled}-01` and `uart-tx-history-uart1-regression-01`.

`run_sustained_screen.py --uart-capture-profile bounded-prefix` changes only UART0 board option and exact adapter component, recording before/after SHA, device-test SHA, prefix capacity, and module. Saved audit reconstructs from original model/board using only declared component difference, then checks final TX sample/total/drop/hash.

## Integrated execution at that time

New cold stock24 60-second run is private `sustained-uart-history-native-01/stock24`. 792 execution source files were frozen in `sustained-uart-history-bw499-01/source/tools` and all SHAs checked. At that point neither 60-second success nor passing the 31-second boundary was claimed.

bw500 `worker.py` in the same directory observed the actual first 60-second run in progress. If first capture was removed/audited/successful, it would reuse it and sequentially execute remaining five 60-second runs → six new integrated six-second runs. Stop on first failure without automatic retry. State is recorded in `state.json`, each original capture, and resource JSONL. During initial wait with state current=None, actual PID/container/exec handle of first capture must be checked.

Earlier repeated six-second runs of three originals are preserved as previous-profile evidence. Overall Goal requires finishing two six-second and two 60-second integrated runs per original plus semantic/UI queue/repeated-frame/cost audits. Three ROM/GPU/GAF gap conditions had already been determined, not precise implementation completed. Physical device/Astra/external publication 0.

## First original run termination

New stock24 ran through 56.988726 seconds post-screen/wall 867.896985 seconds. Execution integrity checks all passed, but it stopped on guard 1 at a new IOM6 HCI transmission, so full 60 seconds failed. UART0 actually transmitted 319 DMA/7021 bytes, recording prefix 4096/drop 2925. Original runtime-exported DMA source bytes were reconnected to independently calculate total length and FNV 383333169706814443, matching observation. Five mutations of actual-data hash/count/drop/prefix/completion were rejected. Original UI queue had messages 0, capacity 96/item 12, ui_task waiting to receive. These are stop-time evidence, not stable 60-second success.

Worker stopped at first failure and did not run subsequent 11. First native container absence and worker termination confirmed. Proof: private `sustained-uart-history-lifecycle-proof-01/report.json`. Next command `010a200100` was confirmed from original stack/buffer and requires separate controller-support contract investigation. Above running-language describes historical status at start.
