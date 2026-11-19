# Raw IMU FIFO storage and read component

bw467. Default-disabled `BlackwallImuRawFifo` was added in `tools/renode-imu-raw-fifo.cs`. **Actual queue, count snapshots, chunked reads, and consumption on full transaction completion were implemented and passed 228 Renode component checks.** It is not yet connected to existing identity peer/IOM/GPIO. Zero new original ARM runs; E12 and overall 10/16=62.5% remain.

## Sources and model choice

The FIFO_COUNT_0/1 register table on page 81 of pinned ICM45608 DS-000595 rev1.1 describes packet count. Section 5 overview of the same document says byte count, creating a discrepancy. Pinned official driver `inv_imu_get_frame_count` and [original FIFO read](imu-fifo-read-transport-contract.md) multiply count by frame size after reading it. This component follows the register table and verified original consumer's packet-count contract. The documentation discrepancy was not resolved by physical reading.

This limited profile supports 16-byte accel/gyro/temperature/timestamp packets and default 2 KB capacity. It accepts only 16-byte frames with header 0x68 and stores at most 128 packets. 8/20/32-byte packets, compression, GAF output, 8 KB expansion, overflow hardware policy, and actual empty-FIFO return are unsupported. Empty data reads are rejected instead of returning arbitrary 0/0x7f.

## State and consumption

- Default off. Enabled state, byte order, and test capacity are explicit. Small capacity is for boundary testing, not physical configuration.
- Input arrays are cloned, preserving stored samples if caller modifies the original array.
- `TryBeginRead(0x12,2)` creates a packet-count snapshot. Two reads do not consume samples.
- `TryBeginRead(0x14,N)` reserves only multiples of existing packets. After `ReadChunk`, `TryFinishRead` on the complete read removes only the reserved prefix and retains newly appended tail.
- Overlapping selection, excess chunk, invalid header/length/address, overflow, and finish/flush before completion are rejected without consumption. No IRQ, sensor readiness, or success response is fabricated.
- Idle `TryFlush` clears only queue and preserves configuration/cumulative diagnostics. `Reset` initializes queue/lease/counters while preserving explicit configuration profile. It does not reproduce physical silicon reset defaults.

Consumption on full transaction completion and snapshot atomicity are explicit model contracts. They do not verify actual partial consumption/restart rules for interrupted transactions. Finish/reselection/flush after partial reads are unsupported; independent test state is discarded by reset. Do not generalize to ordinary I²C abort behavior.

## Verification and preservation

`tools/verify_imu_raw_fifo.py` loads C# source in an actual Renode process; Python does not reimplement the FIFO in its place. It checked both byte orders, array copies, count rereads, order/chunk/commit, tail append, overflow, 2 KB drain, flush/reset/off, and interruption boundaries. The 228 checks include repeated inputs and are not a feature count or overall progress.

First red was a FileNotFoundError for missing source before VM creation, not a native execution failure. After implementation the component suite passed, and owned-container absence was confirmed by journal removed and Docker inspect. Existing model source was unchanged, so prior main/GPIO runs were not repeated.

```sh
<private-python> tools/verify_imu_raw_fifo.py <new-private-output>
```

Output must be a new folder outside the repository. Evidence is preserved outside Git in `simulator/imu-raw-fifo-research-01/`, `imu-raw-fifo-unit-01/`, and full hashes in `imu-raw-fifo-storage-manifest.json`. The [plan](imu-raw-fifo-plan.md)'s storage/consumption unit was closed.

Next are optional identity-peer connection, actual IOM transaction length/chunking/completion, flush register 0x20/reset, and GPIO38 watermark/status configuration conditions. The component does not automatically provide bus responses or GPIO. Normal GAF and gate-0 boundaries remain; natural sensor consumption and screen are incomplete. No physical access, subagents, or external publication.
