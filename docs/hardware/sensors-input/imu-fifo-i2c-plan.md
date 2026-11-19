# Raw FIFO I²C connection plan

bw468. Without modifying the existing identity peer, an optional adapter owns the single IOM4 address 0x69. It delegates initialization, identification, and other transactions to the existing peer and handles only registers 12/14 of an enabled FIFO. A null component defaults to existing behavior. No new sensor/GAF ready flag is created.

Read active TSIZE from the pinned IOM engine's public register collection and reserve the full lease. Actual `Read(min(4,remaining))` and `FinishTransmission` drive chunking and completion. CONT data reads and reselection after partial controller reset are currently unsupported and rejected before consumption or with state remaining. Do not describe this as physical abort/replay policy.

Verification covers WHOAMI delegation, two count reads, data bytes, large bursts and FIFO replenishment, full transaction consumption, default off, excessive/partial length and CONT rejection, and separation of controller/peer reset through actual IOM FIFO. Check both byte orders and reuse the existing startup contract. If possible compare the default delegation path in original main reset/hold with previous SRAM. Do not open the original gate or report an API caller as natural main sensor consumption.

Count/data unit complete. [Execution results](imu-fifo-i2c-transport.md) record the final 176×2 checks, stock 2.4 cold off/on control, and unsupported queued guest flush boundary.
