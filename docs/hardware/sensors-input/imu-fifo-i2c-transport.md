# Raw FIFO I²C/IOM connection

bw468. `BlackwallImuFifoTransport` was connected ahead of the existing initialization peer to handle optional FIFO count/data. **Actual Renode IOM backend transaction lengths, 4-byte chunks, and completion drove reads and consumption of the storage component.** This is not natural sample consumption by original main. Normal GAF and E12 remain incomplete; overall 10/16=62.5%.

## Connection structure

Existing `BlackwallImuIdentity` was unchanged. The adapter is the sole registered peer at IOM4 address 0x69 and delegates identification, initialization, and other transactions to the existing peer. A null or disabled FIFO component uses the existing path. When enabled, only single pointers 12/14 are selected.

The full length of a new read comes from the pinned IOM engine's read-only CMD/active TSIZE metadata. Chunks are returned through actual engine `Read(min(4,remaining))` calls, and the entire lease is committed on actual `FinishTransmission` without CONT. No arbitrary completion flag or normal sensor-ready value is fabricated. Engine source was exact against the existing pinned FIFO-modified version.

The 2-byte count at register 0x12 is a packet count and rereading does not consume it. Register 0x14 accepts only packet multiples in the current raw16 profile. Metadata length 0, invalid lengths, and overreads are rejected. CONT data reads are rejected before reservation; finish/reselection after a partial controller reset is not overwritten as success.

Guest flush 0x20/bit7 with samples remaining is not yet connected to the existing flush state machine, so **it is rejected instead of passed to the existing peer as apparent success**. The internal component's explicit flush API differs from guest flush register support. The existing peer handles the existing initialization flush with an empty queue.

## Actual backend tests

The final little- and big-endian suites each passed 176 checks, including the existing WHOAMI delegation contract:

- Two count reads and byte order, eight chunks of 32-byte data, and packet consumption at actual transaction completion.
- Full byte order of a 2 KB/512-chunk drain and IOM FIFO replenishment.
- Preservation of the remaining lease under IOM backpressure during a long read.
- Controller reset alone does not erase the device queue, and incomplete finish/reselection is rejected. Explicit peer reset initializes queue, lease, and initialization peer.
- Rejection of unaligned reads, CONT, and queued flush, plus default pass-through. On queued flush, the existing peer's WriteAttempts also does not increase, so rejection by the lower peer is not mistaken for adapter guard success.

These are device tests driven by host through actual Renode MMIO/IOM. Python did not fabricate FIFO responses, but these are not sample-consumption tests executing original ARM firmware. Some reset/abort policies are explicit unsupported boundaries and do not guarantee physical replay/partial consumption.

## Preservation of original reset path

Stock 2.4 main reset→existing hold was newly run with the final adapter in FIFO off/on(empty) states. Existing runtime-control audit passed; full SRAM was exact against the existing baseline and between the two runs. FIFO selection/chunk/completion were all 0. This verifies delegation of existing initialization transactions only, not successful natural main FIFO input. Only the diagnostic path to the existing peer object was changed to wrapper StartupPeer; guest PC/branches/returns/TCB/gate were not written.

One initial off control before the queued-flush guard was also preserved. Of three new main runs, two are final-model controls. No claim is made that this adapter was newly run on stock 2.3/Faceclaw main.

The first unit attempt failed due to a missing Python reference to the new C# assembly; the second failed due to a harness error where the reused legacy suite did not reprepare clock/config after controller reset. Both logs were preserved and only test preparation corrected. Results for initial 174, queued-flush guard 175, and 176 including the no-forwarding check are distinguished. The final model was retested after adding the guard; 176 is not a feature count or overall progress.

Saved audit passed 41 judgments and source/capture hash checks. All 11 owned containers were confirmed journal removed and absent in Docker inspect. No new VM was run in the audit.

```sh
<private-python> tools/verify_imu_fifo_transport.py <simulator> <new-output>
<private-python> tools/verify_imu_fifo_transport.py <simulator> <new-output> --big-endian
```

Evidence outside Git comprises frozen source, cold runner, and audit in `simulator/imu-fifo-i2c-research-01/`, unit/cold captures, and full hashes in `imu-fifo-i2c-manifest.json`. The count/data adapter unit of the [plan](imu-fifo-i2c-plan.md) was closed.

Remaining work is the actual ARM/bus connection to original sample consumption, guest flush/configuration lifetime, GPIO38 watermark/status, and normal GAF initialization. Existing GPIO38 gate 0 behavior and unsupported normal sensor computation remain. The model does not produce fusion/GAF results from samples. No physical access, subagents, or external publication.
