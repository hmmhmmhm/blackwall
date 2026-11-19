# 32-byte FIFO parser and M55 transport

bw473 verified ES0/ES1 positions, valid bits, and callbacks in original 32-byte frames, and connected **32 bytes × 10 packets → threshold 10 → original upper consumption → parser/callback/ARM result decoder** on actual Renode IOM. E12 remains partial; overall 10/16=62.5%. This is not the natural GPIO/task path or completed normal GAF initialization.

## Pinned wire profile

| Byte | Content |
| --- | --- |
| 0 | header: ext/accel/gyro, no hires |
| 1 | header2: ES0/ES1 enable, valid bits, ES0 size |
| 2–7 | accel signed16×3 |
| 8–13 | gyro signed16×3 |
| 14–22 | ES0 nine-byte reserved area |
| 23–28 | ES1 six bytes |
| 29 | temperature signed8 |
| 30–31 | timestamp16 |

Pinned TDK `inv_imu_defs.h` and original ARM confirmed header2 bits 2/3 as ES0/ES1 valid and bit 4 as ES0 six/nine-byte selection. Even at size 6, ES1 begins at 23. Event structure offsets were ES0 26 and ES1 35. At size 6, the last three ES0 bytes are not assumed initialized, and padding is not used as a verified value.

In 32-byte state the parser read a timestamp even for header 0xe0 without the timestamp bit. Endianness applied to axes/timestamp; ES bytes passed unchanged. If one gyro axis was -32768, only the gyro mask was omitted. ES0/ES1 valid combinations appeared in event mask 16/32 respectively.

96 runs (three originals × two endiannesses × two ES0 sizes × four valid combinations × two invalid-gyro states) stopped at actual callback entry to inspect events. Another 24 ran two frames each through full original callback return. Original parser/callback executed without ABI stubs; frame size 32/endian and initial ring were explicit isolated fixtures.

## ARM result decoding boundary

When both ES0 and ES1 were valid, original callback called ARM function 0x555388 (stock 2.4), 0x521530 (stock 2.3/Faceclaw). The call did not occur if only one was valid.

This function was separately executed on all three originals with pinned synthetic ES input and returned 0. Its 80-byte output matched across images and was exact against stock 2.4 M55's final output buffer. This verifies **ARM decoding of given ES bytes**, not internal IMU EDMP/GAF calculation, physical sensor-value generation, or meaning of every result packet type. Unsupported normal GAF initialization was unchanged.

Isolated ARM totals 123 runs: 120 parser/callback and three result decoder. Do not add them to new native results and report them as natural boot counts.

## FIFO model changes

`frameBytes` was added to `BlackwallImuRawFifo`. Default 16 bytes/capacity 128 remain. The 32-byte profile specifies capacity at most 64 and applies the 2 KB logical payload limit. Count remains packets; data lease, completion consumption, partial interruption, queue reset, and snapshot-copy contracts remain.

The raw32 profile accepts ext/accel/gyro, no hires, ES0/ES1 enable, and ES0 size 9. It preserves lower ODR/FSYNC/timestamp header bits and ES valid bits. Other frame modes, compression, and ES0 size 6 queue profiles are unsupported. Distinguish size 6 parser tests from model support. Data do not generate GAF results or readiness.

```sh
<private-python> tools/verify_imu_raw_fifo.py <new-private-output> --frame-bytes 32
<private-python> tools/verify_imu_raw_fifo.py <new-private-output>
```

The final 70 raw32 device tests checked endianness, 64 packets/2 KB, count, 512 chunks, partial lease/append, header, length, and reset. Existing raw16 228, big-endian IOM transport 176, and threshold 27 also passed. Initial missing-constructor red and intermediate 64 results are preserved.

## Actual M55 board results

Two stock 2.4 native runs reproduced existing main reset → getter hold; initial full SRAM was exact against the existing cold baseline. Subsequent steps are explicit API diagnosis:

- Host specified frame size 32/endian 0 and inserted ten synthetic packets with distinct axes into the raw32/threshold10 model. Original setter and actual configuration-register lifetime were not yet connected.
- Upper consumer 0x4c38b0 was invoked on the original Sensor Thread/PSP with guest PRIMASK0/BASEPRI0/CONTROL6/IPSR0. Host did not change TCB, IRQ mask, gate, ring, or header.
- Original status → count twice → 320-byte data → parser → callback ten times → ARM result decoder ten times was confirmed. Actual IOM/RTOS/transfer functions were not replaced by stubs.
- Ten packets and four transactions completed; one threshold event cleared. Mutex returned to released and gate was 0. Guard, CFSR, HFSR were 0.
- Original initialized ring header was `(0x10203040,10,10)`. All 2252 bytes matched expectations, including timestamp/raw/float/flags calculated from mode-table period, bias, and scale, and unused slots.
- Final SRAM 3.5 MiB/WORK 64 KiB was also exact in the control with the new intermediate Watch removed. Existing initial observation and completion stop hook remained. This does not claim no effect on all registers, virtual time, or transient writes.

Observation was at 0x4c3ad0 immediately after original parser return, R0=0. Full upper consumer function return remains unverified. Do not confuse isolated callback completion with this native stop scope.

Saved audit passed 65 judgments and absence checks for eight owned containers. New M55 bus integration for stock 2.3/Faceclaw remains unverified.

## Evidence and next steps

Outside Git, `simulator/imu-fifo32-parser-contract-01` contains isolated proof, and `imu-fifo32-research-01` contains native runner, decoder proof, audit, and frozen source. Final native runs are `imu-fifo32-upper-m55-01` and `imu-fifo32-upper-no-watch-01`. File hashes and inputs are pinned in `imu-fifo32-manifest.json`.

Next, per the [original configuration contract](imu-fifo-guest-configuration-contract.md), connect shared FIFO_CONFIG2/decimation and timed 0xa258 paths and let the original setter create frame size. Then connect INT1/GPIO38/task. No physical access, installation, subagents, or external publication.
