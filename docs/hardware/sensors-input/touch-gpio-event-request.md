# GPIO27 sampling and touch-event request path

Follow-up to `bw-0236`. After [configuration synchronization](touch-startup-configuration-model.md), original startup GPIO sampling and attempted event lookup were verified. Actual touch-event data and GPIO edge/IRQ were not yet implemented. This limited model unit is closed, not counted as full touch support or boot completion.

## Original contract

Original GPIO HAL extracts bit 27 from pin27 input word `0x40010404`; wrapper converts it to bool. After a successful read, original startup caller invokes a service function if the value is 0, and returns without that call for value 1 or read failure.

| Point | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| HAL entry | `0x496672` | `0x48a78a` |
| Actual input load | `0x49668c` | `0x48a7a4` |
| Wrapper | `0x4fc898` | `0x5574c0` |
| Startup branch | `0x50511e` | `0x52f0c2` |

`inspect_touch_gpio_contract.py` verified saved original main/manifest, actual stop context, and pad configuration `0x53`. Full HAL and wrapper executed in isolation with actual internal calls/returns; levels 0/1 were compared with all other word bits 0/1. Other bits did not affect the result. Caller success-0/success-1/failure branches were also checked with original fragments. Total 33 original scenarios and 48 checks passed (`touch-gpio-contract-01`). This is not physical idle polarity, voltage, or IRQ verification.

## Optional single sample input

`touchLevel` and separate `touchReadBudget` were added to existing `BlackwallGpioRoleInput`. Default `touchLevel=-1` continues to block the GPIO27 word. Tests explicitly set 0/1 with budget 1.

The sample is supplied only when word address, original HAL read PC, CPU R0=27, guest pad setting `0x53`, and remaining budget all match. Other pins/consumers/configurations/addresses, byte access, and host-context access are rejected. Other bits in returned word are padding irrelevant to this consumer, not known physical GPIO values. No IRQ/edge or pad electrical behavior is generated.

Existing GPIO156 level, five-read budget, and last context are separated from GPIO27 context/counters. GPIO27 reads do not consume GPIO156 budget or overwrite last role pin. Native GPIO 66 checks including defaults and separate default-profile regression 38 passed. Unsupported-profile red was preserved first. Results: `touch-gpio-unit-01`, `touch-gpio-role-regression-01`, red `touch-gpio-red-01`.

## Two level paths in original main

Shared runner and `touch-gpio-high-candidate.json`/`touch-gpio-low-candidate.json` were used. Only core component replacement and explicit input options changed; observer/runtime, original PC/branches/returns, and delays did not.

| Input scenario | GPIO27 samples | Next strict boundary |
| --- | ---: | --- |
| Stock 2.4 level 1 | 1 | PC `0x4966ec`, write `0x100` to GPIO `0x40010468` |
| Stock 2.3 level 1 | 1 | PC `0x48a804`, same write |
| Faceclaw38 level 1 | 1 | PC `0x48a804`, same write |
| Stock 2.4 level 0 | 1 | PC `0x58236c`, IOM5 pointer03 write attempt |
| Stock 2.4 input option off | 0 | Existing PC `0x49668c`, GPIO27 read |

The next level-1 write is GPIO output clear bank4/bit8, pin136 latch write. Current output model requires prior pad configuration and blocks it. Actual output purpose, preconfiguration latch-write contract, and physical signal were not yet verified. Passing GPIO27 sample is not expanded to full touch-input registration return or completion of another thread.

All five runs retained GPIO156 reads=5/last pin156 and configured threshold 800. Success paths preserved existing event prefix and all UART0 bytes/eight IRQs. Off control exactly matched prior CPU, instruction count, observations, and stop. Results: `touch-gpio-main-01`.

## Event lookup diagnosis at low level

Default startup profile still rejects pointer03. Optional `eventPointerProbe=true` permits transmitting that pointer only and rejects all event data reads. It cannot be used outside startup profile. No event is answered with zero or an arbitrary frame.

After additional native red, probe 44 and default startup-profile regression 41 checks passed. Existing pointer03 rejection in default profile was distinguished from unknown-data rejection by event probe. With `touch-event-probe-candidate.json`, low-level stock 2.4 original requested **16-byte read CMD=`0x1002`** after pointer03. New probe stopped at first receive request.

The IOM engine asks the peer to receive in chunks of at most four bytes. Thus **the full original transaction request is 16 bytes, the peer's first request is four bytes**. Guard value 4/peer.LastReadCount 4 must not be confused with the full 16-byte request. Stop PC `0x582242`, address `0x40055120`, operation=`peer-read`. No event bytes were returned at this stage. Total 11 returned bytes are only previously completed version/configuration/status/readback data.

IOM Commands 10/Finishes 9 in the probe run comprise nine completed transfers and one interrupted read attempt. Probe-off control exactly matched existing pointer03 write stop in CPU, instruction count, and observations. Results: `touch-event-main-01`. This establishes the path from initial low GPIO sample to original event request, not actual GPIO IRQ, gesture decoding, or user-input processing.

## Audit and next work

`touch-gpio-verification-01/audit.py` passed 329 checks covering pinned inputs, exact core/peer delta, native logs/observations, reports of 33 original GPIO scenarios, 189 native unit/regression checks, seven main scenarios, and two exact controls. Saved source/model/SHAs prevent retrospective dependence of prior audits on current builders. Python compile also passed.

Next independent contract is the relationship between pin136 output latch and pad configuration. Event work must additionally identify pointer03's 16-byte structure, original decoder, and IRQ clear/reread conditions. Do not fill either unsupported boundary as success. This is not full touch MCU emulation, physical state, full boot, normal font-bank, integrated screen, or web installation/recovery verification. Product fulfillment remains 13/29 (44.8%).
