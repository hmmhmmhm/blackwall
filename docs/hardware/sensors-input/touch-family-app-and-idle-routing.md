# Touch application consumption and idle input routing across three originals

bw445. **Stock 2.4, stock 2.3, and Faceclaw38 all confirmed original main touch → UART peer reply → registered app callback → state change and return to original caller.** Wrong-reply-type controls also passed for stock 2.3/Faceclaw. On stock 2.4, the schedule manager was traced taking input and discarding an idle-state scroll through the original default branch.

Lack of screen change is not immediately treated as missing peripheral or readiness failure. This input code 4 is not an idle-screen invocation input. E11, natural screen, and gesture/ring support remain partial; overall **10/16=62.5%**, API screen 3/6.

## Per-version execution paths

Follow-up [bw446](touch-idle-wake-and-uart-timeout.md) connected double-click → original app 1 UI callback entry and short UART reply timeout. Callback return and pixels remain unverified. Below is bw445's scope.

Existing [stock 2.4 contract](touch-peer-reply-ingress.md) was applied to other originals. Main hashes and actual registries were pinned; UART queue-get, type 1 reply, and receive caller were located separately in original code. Two assumptions of shared internal offsets failed early in source analysis. They were preserved before VM execution, and observation points were instead derived from queue-call and type-branch semantics. A single version address is not simply subtracted.

| Item | Stock 2.4 | Stock 2.3 | Faceclaw38 |
| --- | --- | --- | --- |
| Slider callback | `0x578ce6` | `0x4df68e` | `0x4df68e` |
| Event caller return | `0x443a54` | `0x4440b4` | `0x4440b4` |
| Receive caller return | `0x4fdf3a` | `0x55eac2` | `0x55eac2` |
| App delivery function for reply | `0x465c20` | `0x465f10` | patch `0x7d5824` |
| Last slider tick / role | 5288 / 1 | 5230 / 1 | 5213 / 1 |

These ticks check agreement between original helper returns and actual stored values, not version speed or physical latency.

Faceclaw entered the actual patch. In its `0xf0` check, `0x107/0x108` followed fallback and invoked original registered callbacks. The patch was not bypassed to call stock delivery directly.

Original `uart_sync_thread` read 24 reply bytes and executed wear/slider callbacks in worker0/1. Callback R0=0, actual caller return with same SP/TCB, and receive function's original caller return were confirmed. Replies use original request IDs, channel 0, and `0x0a`; guest SRAM/registers/TCB were exact before/after reply injection.

In both older versions, changing only the valid-CRC reply byte to `0x0b` executed the reply callback but produced no app delivery, state change, or subsequent input packet. Normal/error runs of each image had exact pre-reply SRAM/registers. Unknown-ID control reuses earlier stock 2.4 evidence; it is not claimed newly run on other versions.

## From application to next queue

At actual callbacks across three images, next-stage condition was 0, permission condition 1, and input-dispatch function was called. Subsequent packet:

`0307010004000000a7000a00`

It is type 3, length 12 bytes, role 1/code 4/packed diffX 10 and speed 167. It enters a schedule queue separate from the ordinary UART transmit queue. At stock 2.3/Faceclaw receive-caller checkpoints it remained as one actual queue item; error replies had zero.

In a longer stock 2.4 capture, queue count was 0 and read/write cursors had advanced. The earlier frozen RX checkpoint had one identical packet and was reused as control. Freed heap remnants in final RAM of the longer run are not interpreted as a live packet.

UI type 7 producer/parser observations were zero, and UI queue/ring remained initial. The first description that it “remained in the queue” was corrected for the longer stock 2.4 run. One extra UART IRQ corresponds to original DMA transmission of a type 4 notification produced by the wear callback, not the 24-byte RX.

## Actual idle discard path

Stock 2.4 source classifies type 7 payload in idle. After launch check permits, it handles codes 1, 6, 17, 3 separately; this code 4 follows default discard. Original log string is `idle only support touch bar double click event`. One log string is not used as the complete supported input list; other dedicated branches exist in actual code.

New natural M55 observation confirmed:

| Observation | Actual result |
| --- | --- |
| Schedule-manager queue-get return | Confirmed |
| Payload upper type 7 branch | Confirmed |
| product-test / OTA / silent sample | 0 / 0 / 0 |
| `SVC_Settings_AppLaunchCheck` return | 1, permitted |
| Launch-denied discard branch | Not executed |
| Code 4 default branch `0x467dca` | Executed |
| `0x467e1c` after payload/node free | Reached, same stack/task |
| UI type 7 producer/parser | Zero calls |

The initial launch-denial hypothesis was a test hypothesis based on source conditions and was disproved by execution. Its expected contract and bounded capture were preserved. Host did not fix silent/readiness to force success. No screen change is stock behavior for this idle scroll input.

## Verification and preservation

- Seven new original M55 runs: two older normal, two wrong-type, stock 2.4 UI limit, launch-hypothesis observation, and actual idle-discard terminal.
- Seven final semantic audits passed. All runs had CFSR/HFSR, memory violations, and strict guards 0. Missing planned terminals for UI limit/disproved hypothesis are not counted as screen success.
- Saved-audit assumptions of one UART IRQ and packet presence at every checkpoint failed. New audit distinguishing extra DMA and dequeue evidence and the earlier verifier were both preserved.
- Global task-graph helper did not pass state-container checks on this follow-up RAM. It is not used as evidence of a full RTOS graph or kernel corruption. Task claims are limited to actual entry/return TCB names, SP, Thread mode, and observation scope.
- Private `touch-peer-families-research-01` contains source contracts, builder versions, disproved hypothesis, native verifier, and branch evidence. `touch-peer-families-manifest.json` pins input/output/code/document snapshots. All owned process journals are removed.

No physical access, flash, subagents, or external publication.

## Next experiment

Do not repeat the same scroll or change launch flags. Try screen invocation with virtual touch frames such as **double-click (code 1)** handled by the original in idle. Connect required subsequent display requests/peer replies through original queue/ID/parser paths. After checking whether this reaches actual UI/render/screen, integrate supported input scope and CLI scenarios. Code 17's menu-invocation branch is also a source candidate, not counted as executed success.
