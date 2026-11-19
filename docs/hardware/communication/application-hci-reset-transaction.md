# Investigation of application HCI transmit queue and completion-event consumption

bw-0284. Software behavior units were executed using original ARM and complete SRAM from three verified images, without changing the model or restarting main. This is not a result showing completed HCI Reset exchange in native main. Overall goal remains 13/29=44.8%.

## Successful transmission and queue consumption

The original callback calls ring pop only when the write function returns 0. Error 8 takes the retry path without consuming the queue. The entire original pop function was executed to check requests for 0/1/2 records and wraparound at read offset 1820. With current used 260, one record succeeds and yields used 0, two records fail and preserve state, and read offset wraps to 0.

Descriptor word order is **write offset, read offset, used bytes, capacity bytes, record stride, buffer**. Both producer and consumer multiply stride at offset 16 by record count; producer wraps offset 0 and consumer offset 4 at capacity. Bw283 misnamed the first as stride and fifth as tail based on a snapshot where both were 260. Numeric verification remains valid, but field interpretation is corrected.

## RX and upper event handling

| Item | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| Ring pop | `571e36` | `54c12e` |
| H4 parser | `571eda` | `54c1d2` |
| Upper queue delivery | `5647a4` | `54cdb0` |
| Upper HCI handler | `5647ce` | `54cdda` |

The original parser accepts `04 0e 04 01 03 0c 00`, obtains space through the original allocator, and delivers six bytes after separating H4 type 4 to the upper queue. The result is the same when the packet is split at 1/2/3/6 bytes and supplied in two calls. A six-byte input missing the last byte is not delivered. Stock 2.4 has an additional prior-state cleanup prelude at parser entry, so the same function-relative offset as older versions was not reused.

Then **original pop → optional original parser → original upper handler (event mask 1)** were connected in a synthetic call sequence. This explicitly prepared function-level scenario does not substitute for verification of actual SPI transmission or natural RTOS scheduling. Function calls were not replaced with stubs and original ARM instructions were not modified.

A no-event control remained used 0. Normal Command Complete, a status-1 event, and an event with different opcode `0c04` all queued the same next command. The next record has length 10, opcode `fc43`, parameter length 6. Parameter bytes dependent on the original snapshot remain outside Git. The command was not transmitted.

**Do not treat this path's progress as evidence of correct response opcode/status validation.** Why these three events yield the same result in this initial state, whether they do so in other states, and how a physical controller responds remain unconfirmed. Do not expand this into a general conclusion that all firmware fails to validate events or a security-vulnerability finding.

## Results and reproduction

`tools/inspect_application_hci_transaction.py` checks 54 conditions across three original images: per image write-return 2, ring-pop 4, H4-framing 8, and software-event-pipeline 4. The engine is Unicorn M7 with synthetic entry/register/stack and verified original main SRAM. Distinguish this from natural main progress on Renode M55.

Evidence in the simulator directory outside Git:

- `application-hci-transaction-source-01`: preserved initial 42-condition result.
- `application-hci-transaction-source-02`: 54 conditions including upper-handler controls.
- `application-hci-transaction-source-03`: identical report from reanalysis with pinned dependencies.
- `application-hci-transaction-verification-01/manifest.json`: pins Python 28, four existing models, unchanged web-source SHA, and source report.

The first write-return fragment's error branch encountered an unmapped read because the record pointer on SP used by the original callback was not prepared. The queued-record pointer actually present in original main was explicitly placed on the synthetic stack and checked again. Firmware branches or checks were not bypassed; this correction is not a natural main execution result.

## Next execution contract

Strictly match the virtual controller's third command to actual `01030c00` and provide only the specified normal completion event. At the peer boundary, check that responses with different status/opcode are not treated as normal completion, separately from the two initial commands. The application GPIO consumer must distinguish idle-low from reply-ready-high and not advance the queue before CS/IOM frame completion.

After implementing this contract, confirm actual transmission, response, upper handler, and subsequent queue changes from original reset in all three images. Then continue toward natural app loop and display initialization. This result does not authorize physical writes or open the web installation gate.
