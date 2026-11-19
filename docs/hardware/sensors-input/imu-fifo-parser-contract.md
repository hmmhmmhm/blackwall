# From original FIFO bytes to sample buffer

bw462. The step before the [raw event callback](imu-raw-event-consumer-contract.md) was connected. **In all three originals, the original FIFO parser was confirmed to interpret actual bytes, invoke the existing registered callback, and write the sample buffer.** The bus/FIFO device model, GPIO/IRQ, and natural M55 main sensor consumption are not yet connected. Normal GAF and E12 remain incomplete; overall 10/16=62.5%.

## Call relationships

| Function/state | Stock 2.4 | Stock 2.3/Faceclaw |
| --- | --- | --- |
| FIFO array parser | 0x552fa6 | 0x51f14e |
| Single normal-frame parser | 0x551fe0 | 0x51e188 |
| Event callback | 0x4c4c6c | 0x4b95b0 |
| Saved device structure | 0x20075578 | 0x20075ee0 |

The array parser's actual BL target is the single parser, whose indirect call follows the original callback at device+0x18. The existing natural initialization snapshot was checked to already contain that Thumb pointer. The test did not write a new callback pointer.

Because FIFO frame size in the existing snapshot was 0, size 16 and endianness 0/1 needed for isolated testing were explicitly set. Saved uncompressed state (device+0x1d=0) was unchanged. Sample output ring/header were prepared with synthetic sentinels as in the prior contract. This is not restoration of a completed sensor initialization state.

## Verified data contract

FIFO input is a 16-byte frame: header `0x68` + three signed16 accelerometer axes + three signed16 gyroscope axes + one temperature byte + two timestamp bytes. Axis values and timestamp reached original events in both little- and big-endian. The corresponding valid bit was set for accelerometer/gyroscope when all three axes of that sensor were not -32768. If any axis was invalid, the entire sensor sample was omitted from callback raw/float recording while the other sensor remained.

Four normal inputs × two byte orders × five counts (0/1/2/20/21) ran per original. One axis sign and timestamp varied per frame so success was not judged on simply repeated samples. Original parser entries, callback counts, each event mask/6 axes/timestamp, and order were checked. Count 0 produced no callback/sample write. Original code wrapped the 20-slot ring even for 21 inputs.

Full SRAM per scenario was compared with numeric/ownership expectations; unchanged FIFO input, return 0, and SP restoration were confirmed. Original callback and actual memset/floating conversion helpers executed. There were no bus/callee stubs or PC/return/branch/TCB changes during execution. Function entry arguments and return sentinel are isolated execution fixtures.

An observer-off control was also performed for each original's last pinned scenario (big-endian, 21 frames, both sensors invalid). Full SRAM, test WORK, and R0–R12/SP/LR/PC were exact against observer-on. This is not expanded into a guarantee of no effect for all inputs or FPU states.

Final captures were 40+1=41 per original, 123 total. The first two attempts mistakenly expected temperature bit 4 and stopped after stock24 count 0/1 respectively. Actual mask 11 (accelerometer 1 + gyroscope 2 + temperature 8) and original instructions were checked and only inspector expectations corrected. Axis/timestamp and SRAM checks were already correct; failed events were preserved. Including four additional attempts, 127 actual execution attempts occurred.

## Remaining connections

The pinned TDK [advanced driver](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_driver_advanced.c#L851) separates count/data reads and parsing. The routine immediately preceding the stock 2.4 parser also calls a count helper and then reads `frame_count×frame_size` bytes at register 0x14. This static agreement is not execution verification of bus/IRQ.

Next pin the width, byte order, errors, and ownership of original FIFO count read and read transport, and the sensor task/IRQ path calling this API. Then connect required inputs to the existing virtual bus model. Do not mark GAF initialization complete or turn synthetic calls into successful natural main sensor consumption.

Evidence: `simulator/imu-fifo-parser-contract-01/{probe.py,report.json,event-mismatch.json,preparation-notes.json,manifest.json}` outside Git. Main was rechecked against the verified bundle and snapshot against the bw461 pin. No physical access, model changes, subagents, or external publication.
