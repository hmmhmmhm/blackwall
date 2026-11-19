# Original Re-Advertising and Second Connection

bw402. **After disconnecting, original stock 2.4 main resent advertising parameters and enable, consumed a second virtual connection, and returned through the original connection function.** A separate 1000 ms delay scenario stopped at an unsupported power-control boundary before re-advertising. Keep these outcomes distinct; E14 remains partial, overall 7/16 (43.8%), and API 3/6.

## Optional peer contract

Shared `renode-em9305-reset.cs` remains at SHA `3f830d6c…`. `runtime_reconnect_model.py` checks exact string boundaries in pinned source before creating an optional component. The new boolean defaults to false and can be activated only with explicit disconnect and existing advertising initialization. The board separately selects `runtimeReadvertise: true`.

Re-advertising transmission is allowed only after runtime event 4, when initial connection/ATT/remote feature/disconnect are finished. The following two original commands must match in order, length, and every byte:

| Original request | Declared virtual response |
| --- | --- |
| `0106200fa000a0000001000000000000000700` | `040e0401062000` |
| `010a200101` | `040e04010a2000` |

Response status 0 is a virtual controller fixture, not a value observed on a physical controller. Initial advertising data and scan response are preserved; retransmission is not assumed. After both responses are consumed, a callback pauses the machine and a separate `TryQueueRuntimeReconnection()` injects the second connection event. Previous successful command count 59, response count 60, and all runtime counters are not reset.

Unsupported bytes, order, lengths, connections before completion, and duplicates are rejected. There are no arbitrary ACKs or changes to PC/R0/TCB/SP or connection flags. Original main is unchanged and normal GAF calculation remains unsupported.

## Actual stock ARM execution

After immediate disconnect with reason `0x13`, the original processed both re-advertising commands and responses. The re-advertising segment took 15.0962 virtual ms; second-event injection to original opened return took 4.2964 ms. These are pinned scenario values, not physical BLE performance measurements.

- The second connection event was delivered through GPIO/IRQ → SPI/H4 → original WSF task.
- CCB changed from released to active/state 3, handle `0x40`, peripheral role 1.
- Original task/stack entry and return, one opened-function call, one IRQ, runtime event 5, 11 GPIO edges, and IRQ/pending clearing were confirmed.
- Original opened return address `0x4d3fc4` was reached with zero guard, CPU fault, and memory violations.
- Through initial/ATT/close, inputs outside the model and all SRAM were byte-exact to bw400 immediate disconnect. Previous JSON values also matched. The separate nominal audit's GAF profile mismatch false remains.

The recorded callback time and full-machine pause time differed by 15.3 µs. The initial expectation of identical times was retained as a failure. The callback occurs once within the actual execution segment; consumption of both responses, peer idle, and original final state are checked separately. Execution was not changed or rerun to align timestamps.

A second ATT time setting or complete app reinitialization was not executed. This also does not validate actual RF, normal full boot, completed sensor calculation, or reconnection for stock 2.3/Faceclaw.

## Separate result for 1000 ms delay

The original completed disconnect with sensor request 2/trigger 1 and busy 926. After another 8.3492 ms, actual `str r1, [r0]` at PC `0x494d78` requested `0x40021004 ← 0xEA0`, stopping at power-model guard 1. Re-advertising commands were zero and reconnection did not execute. CPU faults were zero.

This is an unsupported simulator power request, not explicit firmware failure handling or successful reconnection. `verify_runtime_reconnect.py --expect-power-boundary` checks boundary-evidence integrity while retaining `scenario_passed=false`. The aborted machine was not rerun. Next investigate actual preceding power state, changed modules, and quiescent/shared-domain conditions. Do not unconditionally allow the value.

## Checks and preservation

The final optional device model passed 68 checks and the new component passed 31 option-off checks. Actual unit transfers checked fragment preservation, bad bytes, prerequisites, connection before completion/duplicates/replays, exact responses, counter preservation, and reset. Because the startup-state primer uses the same class's command getter, this unit test is not an independent oracle of original startup order.

The first unit test's fragment-deletion bug and two failures after 145 checks of a candidate four-command order are retained: the original sent a second five-byte enable and stopped strictly. In the second failure, final registers, IOM command `0x501`, and R4 buffer were additionally collected to identify the exact enable. The original path was not changed to match the candidate order.

Saved audits comprise 24 immediate-success checks and ten delayed unsupported-boundary checks. Both reports are byte-exact to frozen-tool reports. Three mutations omitting CCB reassignment, completing a response too early, or setting a future callback time, consistently propagated through JSON/log/hash, were rejected. Fourteen progress-management checks passed. New native runs are distinguished as one immediate success, one delayed boundary, and two earlier four-command candidate failures.

Tools: `probe_runtime_reconnect.py`, `verify_runtime_reconnect.py`, `verify_runtime_reconnect_model.py`. Saved audits use new output and do not rerun originals. Private material is retained in `runtime-readvertise-native-{01,02,03}`, `runtime-reconnect-model-unit-{01..04}`, and `runtime-readvertise-reconnect-research-01`.

Existing 16 acceptance criteria and completion states remain unchanged. No physical access, Astra/subagent, or external publication occurred.
