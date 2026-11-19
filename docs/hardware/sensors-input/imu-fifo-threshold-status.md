# FIFO threshold events and original upper-layer consumption

Follow-up bw472: [the original initialization enable branch requests 32 bytes/ES0·ES1/watermark 10](imu-fifo-guest-configuration-contract.md). Raw16/threshold2 below is a separate experimental profile, not completion of that configuration branch.

bw471 calculates threshold events from raw FIFO queue input and executes the original upper consumer function's branches through actual IOM status reads. This is an explicit API diagnosis on the full stock 2.4 board, not natural GPIO IRQ/task consumption or completed normal GAF initialization. E12 remains partial; overall 10/16=62.5%.

## Evidence and supported scope

Page 81 of the pinned ICM-45608 DS-000595 rev1.1 defines FIFO count as a packet count. Page 82 INT1_CONFIG0 specifies threshold status enable bit 1, and page 86 INT1_STATUS0 specifies R/C threshold event bit 1. Pages 90–91 describe watermark 0 as disabled, application on writing the high byte after the low byte, and the FIFO_CONFIG2 bit 3 equal/greater-or-equal condition. The TDK driver also configures bit 3 as greater-or-equal. This is evidence from pinned source and documentation, not physical verification.

The saved [datasheet](https://d17t6iyxenbwp1.cloudfront.net/s3fs-public/2026-06/ds-000595-icm-45608-datasheet-v1.1.pdf) SHA256 is `d73e099df34bee52408b9f46a2ac043b2d67758c2a6f46c9dc58364e63018549`. Comparing watermark and packet count is a supported profile connecting the document's two definitions; it does not verify every boundary behavior of the actual chip.

`BlackwallImuFifoThreshold` defaults to watermark 0 and enable=false. It observes only successful raw FIFO enqueue events. It latches Pending and logical IRQ when the selected packet watermark and comparison condition are met. It does not immediately reassert after a read merely because the queue remains at or above threshold; the next successful enqueue makes a new event. Rejected enqueues create no event.

Watermark, enable, and comparison condition are currently **explicit model constructor inputs**. They are not connected to actual guest writes to 0x16/0x1e/0x1f/0x20, and the LSB/MSB application rule is not implemented. Logical IRQ is not yet connected to GPIO38. Do not treat it as a physical INT1 waveform before pulse/latch, polarity, pad, and mask contracts are verified. It does not generate FIFO_FULL/DRDY/GAF results.

## Status transfer and event lifetime

The existing FIFO adapter with optional threshold handles a 2-byte status transaction at register 0x19 during the active FIFO lifetime. It preserves other status bits from the existing startup peer and synthesizes only the threshold bit. If the lower peer already supplies that bit, it rejects duplicate ownership.

The model supports only complete 2-byte transactions without CONT. It checks the actual IOM CMD/TSIZE and acknowledges the event snapshot on completed `FinishTransmission`. If a new enqueue event occurs after the read, the old snapshot does not clear it. This is a model policy to avoid loss, not verification of all physical byte-level clear timing or concurrent-event handling. Partial/CONT status reads are unsupported.

Device reset clears pending, logical IRQ, and diagnostic counts. The generation is retained so a pre-reset snapshot cannot clear a new event. Existing internal `TryFlush` empties only the queue and preserves the event until read. Do not extend this internal policy to the actual meaning of guest flush. Guest flush with samples remaining is still rejected by the adapter.

## Fix for conflict with original initialization

The first native attempt stopped because it intercepted the existing path that reads reset-done as 1 byte at the same 0x19 address before FIFO input. That aborted machine was not resumed; failure evidence was preserved. It was changed to delegate unchanged to the existing peer before FIFO input/events. Initial full SRAM in two new positive native runs was exact against the existing cold baseline. Initialization flags and branches were not changed to pass.

An unconnected threshold preserves existing behavior; even when connected, initialization before queue input remains the existing peer's responsibility. New C# dependencies were added to two public runners to retain compile dependencies for existing FIFO adapter paths.

## Verification performed

The final 27 device tests drove the actual Renode IOM backend. They checked initial 1-byte reset-done delegation, preservation of non-FIFO status bits, below/reaching threshold, reread/new event, equal and greater-or-equal, watermark 0/disabled, stale acknowledge/reset generations, and preservation of events/lower reads on invalid length or CONT. The startup status peer in these tests is a synthetic fixture, distinct from the original ARM test.

The final model also passed the existing 176 big-endian FIFO transport and 228 raw FIFO tests. The previous 176 little-endian tests were preserved. The initial missing-type red, intermediate 23/26 result, and native initialization failure are preserved separately from final results.

The final stock 2.4 native positive and intermediate Watch-removed control confirmed:

- Full SRAM from reset→existing getter hold matched the existing baseline.
- A synthetic caller invoked upper function 0x4c38b0 on the original Sensor Thread/PSP with guest PRIMASK0/BASEPRI0/CONTROL6/IPSR0. Frame size 16/endian 0, timestamp 0x10203040, and two raw packets are explicit inputs. The host did not write gate, TCB, IRQ masks, ring, or header.
- One threshold event was cleared in the status transaction, and the original executed status→count twice→data→parser→registered callback twice. Actual transfers and mutex/IOM preparation and cleanup are original code, with no bus ABI stub.
- Two packets consumed, four transactions completed, logical IRQ cleared, mutex returned, and gate 0 were confirmed. The original upper function initialized the ring and updated the header to `(0x10203040,2,2)`.
- Execution stopped at 0x4c3ad0 immediately after the original parser returned, with R0=0. **Return from the entire upper function is unverified.** Saved WORK markers/direct API result probes are not used for this stop contract.
- The 2252-byte ring's raw axes, floats, time, flag/index, and unused area matched independent expectations. Final SRAM 3.5 MiB/WORK 64 KiB were exact between the two runs. This does not claim no effect on every register, virtual time, or all transient writes.

Saved audit passed 68 judgments and checked absence of 12 containers. This new connection remains unverified on physical hardware and stock 2.3/Faceclaw.

## Reproduction and remaining boundaries

```sh
<private-python> tools/verify_imu_fifo_threshold.py <simulator> <new-private-output>
```

The upper native caller, audit, and frozen source are preserved outside Git in `simulator/imu-fifo-threshold-research-01`. `imu-fifo-threshold-upper-m55-01` is the initialization-conflict failure; `-02` and `imu-fifo-threshold-upper-no-watch-01` are the final positives. Inputs, provenance, and file hashes are recorded in `imu-fifo-threshold-metadata.json` and `imu-fifo-threshold-manifest.json`.

Next connect the actual configuration lifetime and GPIO38 delivery conditions. Natural main at gate 0 still does not start sensor consumption, and the normal GAF computation contract remains. Do not report this status test as completed natural boot/IRQ consumption. No physical access, installation, subagents, or external publication.
