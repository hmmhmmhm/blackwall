# First IOM7 Request and a PMIC Candidate

bw-0133. The first IOM7 command was observed in original stock 2.4, stock 2.3, and Faceclaw 38 ARM execution without connecting a physical device. Results use existing explicit virtual JEDEC, power, clock, and other assumptions. They do not verify full boot, display, actual PMIC identity, or responses.

## What the original requested

`tools/inspect_iom7_request.py` adds read-only PC observation and first-hit SRAM snapshots to an existing original execution command. It changes no PC, return value, or guest RAM and connects no peer. After calculating instruction addresses, it first checks agreement with each original's actual instruction decode.

| Observation | Stock 2.4 | Stock 2.3 / Faceclaw |
| --- | --- | --- |
| Destination address write | 0x5821d4 | 0x57ae7c |
| FIFO write | 0x582354 | 0x57affc |
| CMD write attempt | 0x58236c | 0x57b014 |

All three runs passed these points once in order. Immediately before address write, R0 is **0x6b** and the target register is IOM7.DEVADDR (offset 0x2c4). Transfer structure size is 2, transmit pointer is 0x2007fa0c, and its RAM word is 0x00000905. Immediately before FIFO, `ldr r1,[r4]` → IOM base calculation → `str.w r1,[r3,#0x10c]` was compared with R1=0x905 at the actual stop. Two bytes sent to little-endian FIFO are **05 09**. The observer itself did not record R1, so saved final CPU context and instruction decode were used together.

CMD 0x201 is command 1/write, size 2 in the current model. With no peer it strictly stops, so completed bus transmission, ACK, subsequent read, and actual PMIC register change were not observed. Allowed Commands and CQ pairs are 0, and UART ISR is also 0, matching the previous endpoint.

The structure ABI was not inferred and copied from public HAL names. Instructions and snapshots confirmed the actual callee reads address at offset 0, length at 0x10, and TX pointer at 0x18. Some other field meanings remain unknown.

## Candidate: Nordic nPM1300

Original code contains npmx ADC and charger driver strings. They alone do not establish the actual part or IOM connection. Current [Nordic public driver](https://github.com/nordicsemi/npmx) source was pinned to commit `4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f`; relevant ADK, driver, backend, and LICENSE were investigated. Each file's SHA-256 and Git blob were checked.

The [pinned nPM1300 register definitions](https://github.com/nordicsemi/npmx/blob/4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f/adk/npm1300.h) define ADC base 0x0500 + ADCCONFIG offset 0x09. Thus interpreting 05 09 as high/low bytes of a 16-bit address is consistent with pointer setup for an nPM1300 ADCCONFIG query. Nordic public material's seven-bit TWI address 0x6b also matches, but shared addresses are possible and no actual read was observed, so it remains a **PMIC candidate**. The backend merely passes addresses to a platform callback; this source alone does not prove G2 wire encoding or the entire subsequent transaction.

The header's ADCCONFIG reset 0 is not actual device state. The original may inherit existing boot/PMIC state. A peer returning 0 at this address is not automatically connected.

The repository root LICENSE and some drivers are BSD-3-Clause, but ADK headers have separate terms including Nordic-IC-only use. The whole repository is not treated as BSD. This work investigated source only; ADK was not copied or compiled into Blackwall execution code or connected to the model.

## Preserved failures and verification scope

The first `iom7-request-observation-01` failed descriptor checks after one stock 2.4 run. SP+44 was incorrectly selected as the transfer structure; the actual structure was SP+80. Destination 0x6b and a FIFO candidate were observed, but the failed run is not counted as passing all checks. The first tool copy was also preserved. Corrected `iom7-request-observation-02/report.json` passed for all three inputs.

The 81 checks in saved audit `iom7-request-verification-02/report.json` compared raw logs/reports, observation markers, current host source, pinned main/image, FIFO load/store and payload, identical stock 2.3/CFW model/runtime, and Nordic source hashes/blobs. The first audit rejected expected mnemonic add.w versus actual adds.w; the expectation was corrected and the audit performed in a new directory. Native was not rerun for this correction. A note erroneously reusing start time was corrected in an append-only row.

Next, compare address encoding, repeated START/STOP, and read-modify-write contracts in the original caller and public PMIC documentation, then define an explicit virtual peer limited to verified addresses. Do not pass all power, charging, sensor, and OTP behavior with generic ACK/0.

Product completion remains 13/29. No physical-device writes or Astra calls occurred.

Independent reading review was performed by the same GPT-6 family (exact ID unconfirmed). It found no forced branches or guest-state changes and identified the timestamp correction and separate payload evidence comparison; both are incorporated above. The reviewer did not rerun native, verify a physical device, or compare transcript archives. Nordic address reference: [TWI section of the public official nPM1300 specification](https://devzone.nordicsemi.com/cfs-file/__key/communityserver-discussions-components-files/4/nPM1300_5F00_OPS_5F00_v0.7.pdf).
