# Original FIFO read and upper consumer function

bw463. The actual read path preceding the [FIFO parser contract](imu-fifo-parser-contract.md) was connected. **The original upper function executed interrupt status → FIFO count twice → FIFO data → parser → registered callback → sample buffer write.** This resulted from explicit I²C ABI responses in isolated Cortex-M7 execution. It was not verified on the virtual IOM4 bus/GPIO/IRQ or natural M55 main, and normal GAF remains incomplete. Overall 10/16=62.5%.

## Original call relationships

| Function | Stock 2.4 | Stock 2.3/Faceclaw |
| --- | --- | --- |
| Upper sample consumer | 0x4c38b0 | 0x4b81f4 |
| FIFO count/data API | 0x552f7c | 0x51f124 |
| FIFO array parser | 0x552fa6 | 0x51f14e |
| Original platform read callback | 0x4c2186 | 0x4b6aca |
| I²C transfer ABI boundary | 0x551a62 | 0x51dc0a |

The upper function started at its original entry. Register 0x19 response `02 00` explicitly supplied FIFO threshold status, and original control flow selected FIFO consumption. Platform read callback and original driver/helper/parser/memset/sample callback executed. In success tests synthetic responses were supplied at one I²C transfer function boundary. Controller 4, address 0x69, one-byte TX register, and RX pointer/length were checked against actual arguments and caller stack. That ABI return is a stub, not natural integrated execution.

Existing snapshot callback and read pointers were retained. Only FIFO frame size 16 and endianness 0/1 were selected as isolated-test configuration. **The original upper function itself cleared the 2252-byte sample ring and set its header.** Unlike the prior test, the host did not prepare output ring/header.

## Actual transactions and error contract

The success path transactions are:

1. Register 0x19, two-byte interrupt status read.
2. Register 0x12, two-byte count read.
3. Register 0x12, two-byte count reread.
4. Register 0x14, `second count×frame_size` byte FIFO read.

The count helper converts the second value in the selected byte order. The first response was count+1 and the second count, distinguishing this from success with identical responses. Even at count 0, the original API attempted a zero-length data read. This is not expanded into a claim that the current Renode bus model supports it.

In 24 upper runs (three originals × two endiannesses × count 0/1/2/20), actual callback mask/axes/timestamp/order, ring raw values/time/index, and zeroed unused area were checked. Observation stopped immediately after the upper function's parser call. Return of the entire root and subsequent distribution/application notification were not completed.

The 24 error controls replaced the original platform read callback at a separate boundary with an ABI stub, supplying normal status or an error in first count/second count/data respectively. **All three reads were attempted even on error, and the driver converted nonzero serial status to -3 and accumulated the return.** SP/SRAM preservation, count conversion, and preservation outside specified buffers were also checked. This synthetic contract supplies read data despite error and does not claim data validity on an actual failed bus. It also does not fully verify platform error recovery or physical hardware error handling.

## Upper gate and next connection

The consumer function's original BL caller is stock 2.4 `0x4c5fd4`, old2 `0x4ba918`. The wrapper first checks a word and does not call the consumer if it is 0. Gate slots are `0x200774f4` and `0x20077d00` respectively, both 0 in saved snapshots. The immediately adjacent timestamp slots were also 0.

Three controls executing the wrapper with saved state unchanged returned without entering the consumer and left SRAM unchanged. The gate's exact meaning and producer were not yet identified. Do not immediately name this 0 a GAF initialization failure flag or particular IRQ state. **Next identify the original GPIO/IRQ producer updating gate/timestamp and its task call relationship.** Do not write gate 1 from the host.

A total of 51 isolated ARM runs were performed (24 upper + 24 driver error + three saved-gate). Model and original firmware were unchanged. No physical access, subagents, or external publication. Evidence is outside Git in `simulator/imu-fifo-read-contract-01/{probe.py,report.json,caller-gate.json,manifest.json}`. Normal GAF, FIFO device model, and natural IRQ/task consumption remain E12 conditions.
