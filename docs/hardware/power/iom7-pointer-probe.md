# Original Read Request After a Virtual IOM7 Pointer

bw-0134. This is an explicit experiment to identify the original firmware's next requirement. It does not verify actual PMIC identity, data, behavior, full boot, or display. It follows the [design scope](iom7-pointer-probe-design.md). The default main runner was unchanged.

## Implementation

`renode-i2c-pointer-probe.cs` is a virtual II2CPeripheral peer. Only in an experiment explicitly connecting it to IOM7 address 0x6b does it accept two bytes 05 09 as address pointer 0x0509. Other writes, lengths, fragments, and duplicate pending requests are blocked. FinishTransmission preserves the pointer and clears pending; the same pointer may then be set again. Every Read stops with CpuAbortException instead of returning a value or empty success. This is an experiment condition accepting a virtual pointer write, not reproduction of actual PMIC ACK. Nordic ADK code was not copied or included in executable code.

Twenty checks in independent direct-call test `i2c-pointer-unit-01/report.json` confirmed normal pointer/finish/repeat/reset, invalid address/length/null/pending, rejection of every read, and pointer preservation.

## Three original runs

`tools/probe_iom7_pointer_main.py` copies bw133's pinned native inputs to a new directory. Only peer source, explicit board connection, and guard/peer diagnostics were added. Main, SRAM/ITCM fill, and probe were preserved byte-for-byte; CPU/memory policy and original instructions were unchanged.

| Input | Pointer write / Finish | Next actual request | Stop PC |
| --- | --- | --- | --- |
| Stock 2.4 | Once each | One-byte read at 0x0509 | 0x582242 |
| Stock 2.3 | Once each | Same | 0x57aeea |
| Faceclaw38 | Once each | Same | 0x57aeea |

The original next CMD value is 0x102, consistent with an IOM7 read size 1 request, and actual peer Read(1) was called. The saved original transfer structure also contains address 0x6b, length 1, direction 1, and an RX pointer. Commands=2 counts acceptance of pointer write and **attempt** of the read command, not two completed transfers. Read response, RX data, second Finish, and subsequent caller return were not observed. Since execution stopped at the read boundary, no PMIC configuration value write is claimed.

Existing read-only instruction observation was retained. Original 2.3/CFW model, board, and diagnostics are identical; runtime differs only in original main length. UART TX, ISR, and CQ pairs are 0 and integrated display remains incomplete.

## Specification comparison and remaining uncertainty

[Current Nordic TWI documentation](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/ctrl_reg/doc/frontpage.html?contentId=7TMWQN9EhrHwW0KklAwnCg) describes seven-bit address 0x6b, 16-bit register address, eight-bit data, high-byte bank and low-byte offset. The [current ADC map](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/saadc/doc/frontpage.html-topic?contentId=kbYy939w3WVOjAcX7hfJHQ) base 0x0500 + ADCCONFIG 0x09 also matches the request. This supports the nPM1300 candidate, but differs from identifying the actual part.

Online text was checked, but the latest PDF fetch returned 530 and timing SVG download returned 403/tool unsupported, so the diagram was not reviewed. Actual protocol compatibility for START/STOP, repeated START, and pointer retention is not established. These remain explicit acceptance conditions of the virtual peer only. The current virtual Apollo510 SKU/GPU configuration consistency limitation also remains.

Next, statically trace how the original read caller uses ADCCONFIG and determine scope for explicit virtual register state consistent with public specifications. Do not return arbitrary 0 for unverified registers or replace main functions.

## Verification and preserved failure

The first `iom7-pointer-main-01` stock 2.4 already observed the next read, but final verification failed because frozen reporter constant peer_attached=False remained. Failure material and runner were preserved. `iom7-pointer-main-02/report.json`, reflecting explicit IOM7 connection in derived diagnostics, verified three originals. The default runner's unconnected peer state is unchanged.

The 53 checks in `iom7-pointer-verification-01/report.json` compared unit raw markers/current source, original main/image and base/derived hashes, unchanged fill/probe, exact added source and diagnostic code differences, original read CMD/transfer structure, single strict stop, and absence of policy violations. parse_log also checks unexpected warnings/errors/runtime exceptions. This is not counted as separate real-device/full boot verification. Product conditions remain 13/29.

No Astra, physical-device work, or external GitHub publication occurred. Independent review scope and findings are preserved in the final private verification folder.
