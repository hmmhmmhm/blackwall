# MSPI1 Array RX Streaming

Task bw-0197. Advanced the 172-byte `nvSysDt` read after [blank NVdb](nvdb-blank-scenario.md) initialization. Implemented logical streaming retaining a 16-word FIFO capacity; all three originals consumed the data and stopped at the next power request. Full factory-initializer return, whole boot, and display had not yet been confirmed.

## Source and model contract

Pinned HAL commit `61b293a49db34030c545f99101f7ebf6a3050314`'s `am_hal_mspi.c` follows CTRL start → RXENTRIES wait/RXFIFO drain → CTRL completion wait, distinguishing full words and leftovers. `am_hal_mspi.h` specifies a 16-word FIFO. Independently compared source SHA-256 and CTRL store/RX helper/completion-wait BL in three original mains. Correspondence to public HAL does not verify every physical peripheral cycle.

`BlackwallMspi1PioReset.maxArrayReadBytes` keeps default 64. The opt-in limit is 64..65535; above 64 requires explicit backing. Long transfers were allowed only for original runs specifying CLI `--array-read-limit 256`. Existing backing range, opcode, configuration, timing/DDR, and QE/WIP conditions are still checked.

The existing completion path for reads up to 64 bytes remains. Long reads proceed as follows:

1. Validate the requested range and retain bytes from declared backing. CTRL is busy; no data or completion exists yet.
2. At each mock 10 µs service tick, supply as many words as FIFO has free slots. If full, retain pending position and wait again. Guest reads do not immediately refill FIFO.
3. Set CTRL completion and IRQ pending when the last byte enters FIFO. The guest may not yet have read the final FIFO data, so controller off is rejected while unread data exists.
4. A clock-epoch change or power mismatch aborts transfer at the next service and discards partial FIFO/pending position. Reset also cancels timer and offset. RAM already read by the guest is not rolled back.

The 10 µs supply interval is an existing logical-transport mock timing assumption, not measured physical bit clock, bandwidth, latency, or power. Discarding partial FIFO on clock abort is also this experiment's policy, not a physical clock-loss result. `ArrayReadTransfers` and `ArrayBytesRead` count only completed full transfers, so partial bytes consumed by the guest before abort are excluded.

## Tests

Unit/regression total: 402 conditions:

- 172 bytes: 79; 173 bytes: 80. Covered ordering, partial-word padding, full 16-word backpressure, partial drain/refill, completion/IRQ order, busy-command and off rejection, clock abort, stale RX prevention after Reset, and short retry.
- 65 bytes: 31; 256 bytes: 82. Covered actual transfer at the streaming threshold and selected maximum, final word, and prevention of reappearance.
- Stuck: 11. With `CompleteTransactions=false`, even a retained long request creates no FIFO/completion/IRQ, and no stale data appears after Reset.
- Existing array 46, page program 29, continuous status 44 regressions.

The first red run failed at platform load because the new constructor argument was absent. In the first test after implementation, fixed an incorrect assumption that the final 19-word batch was supplied at once. Also corrected the second test's IRQ clear address to existing register-contract address `0x40061208`. Initial failure logs were preserved separately and not treated as firmware errors or passing evidence.

## Original execution results

Stock 2.4, stock 2.3, and Faceclaw 38 each ran unchanged pinned main bytes from main reset. PC/branches, returns, and delays were not forced. Existing synthetic identity, power, memory, and logical SDR assumptions remain. This is not proof of full ROM/bootloader boot.

Each original completed 507 array transfers, 10,939 bytes: exactly one transfer and 172 bytes more than before. Last address was `0x1ff80a1` and all FIFOs were empty. This supports progress through the 172-byte transfer and guest FIFO consumption. Physical validity or configuration meaning of `nvSysDt` contents was not verified.

Program count 242, erase count 128, and all content-change counters match the prior blank-NVdb run. Controller off increased 873 → 874; XIP restorations remained 873. The next request was a write of `0x08000400` to PWRCTRL `0x40021004`; this unsupported request was blocked. Meaning and power behavior of the new peripheral had not yet been analyzed or allowed.

PCs were stock 2.4 `0x494d78`, stock 2.3/Faceclaw `0x488e90`. The prior 2,596 selected observations, zero drops, and complete observation object were identical. Peripheral behavior advanced, but there was no additional NVdb stage; factory-initializer return or magic-mismatch rebuild was not reached. Existing compact-storage excluded labels remain as documented; do not interpret this as a full instruction trace.

A stock 2.4 baseline without the new limit matched the previous board and retained the 172-byte-read blocking boundary. Compiled model, original main, derived assets, and logs/reports were also checked.

## Evidence and next steps

Outside Git under `simulator/`:

- `mspi1-rx-stream-unit-03`, `padding-01`, `boundary65-01`, `boundary256-01`, `stuck-01`, and `array-regression-01`, `program-regression-01`, `status-regression-01`; common prefix `mspi1-rx-stream-`.
- `mspi1-rx-stream-main-01/{stock24,stock23,cfw,stock24-default}`: four native conditions.
- `mspi1-rx-stream-verification-01/report.json`: 120 checks comparing source pins, original calls, current compiled model, unit logs/reports, asset hashes, observation preservation, 172-byte consumption, next guard, and default preservation.

A read-only review by an agent inheriting the parent model reported no Important/Critical defects. Suggested 65/256 boundary and stuck tests were added and the limitation of partial-consumption counters stated. Astra was not used.

Next investigate bit meanings of the new power request, preservation of other peripherals in the shared request word, and the original caller. Do not make unknown requests succeed or delete existing UART/ADC and other power checks.

There was no glasses scan/connection, RAM payload, OTA, flash, or MRAM write. Whole boot, integrated display, and physical installation/recovery remained incomplete; overall product completion stayed 13/29, 44.8%.
