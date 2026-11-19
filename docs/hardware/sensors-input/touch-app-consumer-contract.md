# Touch message transmission and application consumption boundary

bw443. **GPIO27 IRQ → input task → wear/slider messages → UART0 DMA transmission completion** was confirmed in original stock 2.4. Actual registration tables were also checked in three images. Application callback execution, app state, and screen change remain unconfirmed. E11 is partial; overall **10/16=62.5%**.

## Messages confirmed in existing execution

Original main and before/after SRAM were verified using bw442's pinned manifest. The actual input task created two common transmit-queue entries; the host did not write nodes or callbacks.

| Item | Wear notification | Slider |
| --- | --- | --- |
| Identifier | `0x107` | `0x108` |
| Content length | 8 bytes | 12 bytes |
| Content | type 3, proximity 2, role 1 | role 1, code 4, diffX 10, speed 167 |
| Queue packet type / completion callback | 1 / 0 | 1 / 0 |

Stock 2.4 producers are `0x4b7ff6`, `0x5788a0`, calling common broker `0x46a79c`. Broker queue slot is `0x200775dc`, actual queue `0x200752c0`, capacity 150×4 bytes. This differs from the input task's own 30×12-byte queue. Do not interpret the handle at `0x20077754` notified by the broker as a TCB. Original call uses the event flags API.

| Original | Registrations | Event dispatcher | `0x107` callback | `0x108` callback |
| --- | ---: | --- | --- | --- |
| Stock 2.4 | 52 | `0x443a1c` | `0x4b821c` | `0x578ce6` |
| Stock 2.3 | 46 | `0x44407c` | `0x4adf60` | `0x4df68e` |
| Faceclaw38 | 46 | `0x44407c` | `0x4adf60` | `0x4df68e` |

The second word of a registration row is the event callback, distinct from the third word used by separate UI type 2 dispatch. Actual table pointers, original dispatcher `row+4` load/BLX, and ARM callbacks in each image were compared. This table is source/saved SRAM evidence, not natural execution success for all three callbacks.

## Support for subsequent GPIO read

The first stock 2.4 follow-up stopped strictly at `PC0x49668c / address0x40010404` because the existing GPIO adapter supported only one fixed touch sample at startup. The original HAL path rereading pin27 after input-caller return was not skipped.

`BlackwallGpioRoleInput` was connected to read current `Pin27High` from an opt-in `runtimePin27` controller when present. Original read PC, pin27, PINCFG27=`0x53`, 32-bit access, and finite read-budget checks remain. With runtime option off the existing fixed-sample contract remains. The read itself neither creates nor clears edge/pending.

Two virtual inputs were checked on stock 2.4:

- Pulse: explicit high 1 virtual ms after falling edge. Initial/subsequent samples high/high, with actual IRQ56 and frame read between.
- Held-low: no high after falling. Initial/subsequent samples high/low. Original code transmitted the same two messages in this case too.

Both confirmed read budget 2, 16-byte frame/four chunks, original input-caller return, and original GPIO pending/IRQ clear. Physical touch MCU read-clear behavior and pin-release timing were not verified. A unit control also checks that reader reset does not reset the external source.

## Actual transmission and remaining boundary

Follow-up [bw444](touch-peer-reply-ingress.md) connected valid peer reply → original registered callback → state change/caller return for stock 2.4. Below is the bw443 result; screen and other-image integration remain incomplete.

In final pulse and held-low captures, the last two of 12 original UART0 DMA completions were `0x107` and `0x108` packets respectively. Actual request IDs `0x800a`, `0x800b`, channel 1, length/content, and CRC were verified. Common transmit queue returned to 0.

At the 100 ms observation limit with existing GAF parameter profile, original code was at `0x5821d4`, and CFSR/HFSR, memory violations, and strict guards were 0. Registered callback and local dispatch helper observations were 0. This does not mean normal GAF computation, full boot, screen, or physical latency success. Poll-based host observation does not establish an exact 100 ms endpoint.

Original stock 2.4 type 1 normal reply callback `0x468ca4` extracts original request identifier/length/content and passes them to `0x465c20` when the reply's first byte is `0x0a`. This path was not called in the capture. **UART transmission completion and valid peer reply reception are separate.** Next verify a minimal virtual opposite-glasses reply contract linking actual pending request with original receive parser, CRC, and correlation ID. Do not substitute direct callback calls or app-registration manipulation. Event dispatcher after local delivery must also be connected separately.

## Verification, preservation, and limits

- Source/pinned SRAM audit for three images. Only stock 2.4 had four new main runs: first strict frontier, pulse prototype, final pulse, held-low.
- Initial GPIO frontier and pulse prototype were preserved. Starting registers/full SRAM in final two runs were exact against the first. Guest registers/full SRAM before and after IRQ injection were also exact. No universal runtime-hook neutrality is claimed.
- Final device checks: 79 passed, including existing fixed-GPIO checks. New cases cover invalid context/off-source rejection, high/low/re-rising/second edge, finite budget, and reader/source reset separation.
- Red was missing new method. First green attempt's IronPython optional/out argument combination failure was preserved and existing three-argument overload restored. Final public verifier is `tools/verify_gpio_role_input.py ... --touch --runtime-touch`.
- Source/semantic reports and builder/verifier in private `touch-app-consumer-research-01`, four native captures, and red/green/final unit captures are pinned by `touch-app-consumer-manifest.json`. All owned process journals are removed.

No physical access, flash, subagents, or external publication. E11 app/UI and gesture/ring scope was not reduced and is not completed on transmission success alone.
