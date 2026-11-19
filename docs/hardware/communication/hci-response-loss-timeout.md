# HCI response loss and original timeout path

Follow-up bw406 explained the time difference through this clock profile's RTOS 1024 Hz and original WSF epoch/integer subtraction ([tick accounting](../../research/wsf-tick-accounting.md)). Physical clock/SI ten-second accuracy remains unverified; the unexplained account below records the state at bw405. Existing evidence and flags are not changed retroactively.

bw405. **Dropping one specified readvertising response caused the original WSF timer to expire and entered stock 2.4's actual timeout callback and reinitialization call path.** Reinitialization stopped at the existing controller replay guard. Observed virtual elapsed time for the ten-second setting was 9.760541 seconds, so timing accuracy is not judged a pass. Overall 7/16 (43.8%), E14 partial, and API 3/6 remain.

## Differences between public source and original

Previously compared Cordio commit `54e8693ef4ff7e025018094f290a1d5cf380941f` [`hci_cmd.c`](https://github.com/ARMmbed/mbed-os/blob/54e8693ef4ff7e025018094f290a1d5cf380941f/connectivity/FEATURE_BLE/libraries/cordio_stack/ble-host/sources/hci/dual_chip/hci_cmd.c) defines command timeout as two seconds and its timeout function only traces. A new file was obtained after checking directory metadata, Git blob, and SHA. It was not assumed to be the actual G2 implementation.

The send function was located in the command-ready helper of all three stock 2.4/2.3/Faceclaw binaries, confirming:

- The opcode to send is saved, then 10 is passed to original `WsfTimerStartSec`.
- The seconds wrapper multiplies by 100 and passes it to the common timer function: a 1000 WSF-tick setting.
- Owner 0's wrapper calls the common HCI handler, which calls the original timeout callback for message event 1.
- The timeout callback has six original subsequent calls, unlike the public reference that only traces.

Stock 2.4 timer/credit/opcode addresses are `20075f64/20075f86/20075f84`, and callback `563d00`. Credit offset is `0x1a` in the other two originals, different from 2.4's `0x22`. Per-original addresses, instruction bytes, and call graph are pinned in the private contract. This is source analysis of three originals; the actual native experiment below uses stock 2.4.

Initial assumptions of a direct owner-wrapper call and then a common credit offset each failed assertions. A new contract was made after confirming wrapper→inner handler and per-original offsets. Failed scripts and source material are retained.

## Fault model and healthy control

`runtimeDropFirstReadvertisingReply` defaults false and requires an explicit readvertising profile. After receiving the exact first original readvertising request `0106200fa000a0000001000000000000000700`, it drops only one Command Complete. Actual sent-byte verification, original timer, credit, memory, and branches are unchanged. No fake timeout, disconnect, or success response is generated.

Fifty-five device-model checks confirmed one drop, no response/ready edge, rejection of early reconnection, reset, and constructor prerequisites. The same model with option off passed the existing 68 checks. These unit tests do not execute firmware.

Both original runs reused the existing shared-IOM profile, sensor execution-stop fault, and 1000 ms delayed release. Full SRAM and three JSON values through ATT/close were byte-exact/value-identical to previous canonical material. Timer observation was installed only afterward.

## Actual native observation

| Item | Normal response | First response lost |
| --- | --- | --- |
| Original setting | 10 seconds · 1000 WSF ticks | Same |
| Readvertising command/complete | 2/2 | 1/0 · one drop |
| Original timer cancellation | `WsfTimerStop` returns and active 0 after enable response consumed | None |
| Original timeout entry | None | Event 1, timer embedded message, original WSF task/stack/LR |
| Subsequent path | Pause at timer-cancellation observation | First five callback BLs executed, next controller RDY boundary |
| CPU fault/guard | 0/0 | 0/existing guard 1 |

At loss, original credit was 0, opcode `2006`, timer 1000 ticks/active 1. After expiration remaining ticks became 0/active 0, and the original handler received timer+8 message `00 00 01 00` and executed the callback. Opcode `2006` was passed to the first callback call, argument 200 to the second. No arbitrary API caller or PC/R0/TCB/SP setting invoked the callback.

The healthy control ends immediately after timer cancellation, before the next original credit=1 store. Credit 0 at that point is not interpreted as cancellation failure. It is not a control running through full advertising-function return or a new connection.

## Time difference and recovery limitations

Virtual time from original timer-start observation to timeout entry was 9,760,541,000 ns, 239,459,000 ns short of ten seconds. Original 10/1000 ticks were not reduced, and clock or branches were not changed to match the difference. At that time WSF elapsed-tick accounting, clock model, and observation effects had not been isolated. `timing_accuracy_verified=false` and `observer_neutrality_verified=false` are explicit. This is not evidence of actual hardware ten-second accuracy or physical BLE performance.

During subsequent callback reinitialization, the peer became `Exhausted` under the existing single-use contract and stopped at original PC `50190c` reading GPIO117 RDY word `40010410`. Callback return, sixth call, recovery completion, and final consumption of app error notification were unverified. The guard was not removed and the aborted machine was not resumed.

Sensors retained request 2/trigger 1/pending and calculation 0. Busy reads rose to 12454, but are not counted as normal GAF calculation. Unlike an earlier test injecting controller reason `08`, this one dropped the response itself and observed original timer expiration.

## Audit and next work

Twenty-one saved audit checks cover exact model/board/observation extension, original/full prefix SRAM, credit exhaustion, timer activation/expiration, WSF call context, subsequent call prefix, normal cancellation, and exact recovery guard. Existing nominal audit's false GAF/same-second RTC expectations were retained. The report distinguishes timeout observation from unverified recovery/timing accuracy.

Three cases consistently tampering with incorrect timeout event, credit not exhausted at loss, and unexpired remaining ticks across JSON/log/hash were rejected. Frozen audit reports were byte-exact and 14 progress-management checks passed. New native runs were one healthy control and one loss; host 75-second/virtual 11.5-second observation ceilings are separate from original timer setting.

Next trace the WSF tick elapsed-time difference first and pin controller replay prerequisites and lifetime/budget for the actual reinitialization path. Do not unconditionally replay full initialization or auto-ACK. Other originals' native timeout, normal GAF, full app, and full E14 completion remain unverified.

Tools: `hci_response_loss_model.py`, `renode-hci-timeout-observer.cs`, `verify_hci_response_loss_model.py`, `probe_hci_response_loss.py`, `verify_hci_response_loss.py`. Private evidence: `hci-response-loss-{native-01,unit-01,unit-off-01,research-01}`. No physical device, Astra/subagent, or external publication.
