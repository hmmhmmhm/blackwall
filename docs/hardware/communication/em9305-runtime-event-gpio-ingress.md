# Controller runtime event and GPIO117 IRQ ingress

bw374, E13/E05. **M55 execution in three originals connected virtual controller event → GPIO IRQ59 → original SPI/HCI → `ble_wsf` task → connection-block creation without an API caller or PC/TCB/SP seed.** Runs progressed from original main reset to the existing normal hold, then a device event was supplied and execution resumed unchanged. This is not full natural initialization, ATT app messaging, or physical BLE verification.

## Implementation contract

Existing EM9305 peer and GPIO owner were extended. Defaults are disabled and previous profiles unchanged.

- `runtimeConnectionEventHex` is selectable only with an advertising startup profile. Currently it supports one explicitly specified 22-byte successful peripheral LE Connection Complete event.
- Enqueue requires startup `Complete`, CS known/high, GPIO117 config 93, group 3 bit 21 enabled, and runtime link connected. Mid-startup, invalid config, masked ingress, duplicate or post-consumption enqueue are rejected before state changes.
- Runtime link delivers ready rising to the same GPIO owner. It latches pin117 pending bit 21 and outputs IRQ59 combined with enable. In SVD PINCFG117 IRPTEN[7:6], 93 matches rising-edge setting 2.
- Original ISR clear lowers pending/IRQ. Even if ready stays high afterward, no new pending is created without a new rising edge. Masking lowers only IRQ and preserves pending; unmask raises it again.
- Existing SPI header/payload/CS state machine is reused. Runtime consumption commits and ready lowers at CS release after the last payload. Startup command/reply and runtime event consumption counts are tracked separately.
- CS release during a partial header permits retry of the same event. Controller abort is blocked via existing Fault path. Reset clears owner, pending, line, and runtime consumption state. No arbitrary automatic reconnection/rearming was added.

Other GPIO pins, software set, and general electrical/timing models were not implemented. Scope is optional pin117 rising-edge input and original status/clear boundaries. This is not measured physical waveform or IRQ latency.

## Native results

| Target | New native judgments | Saved semantic audit | Actual task | Connection handle / ID |
| --- | ---: | ---: | --- | --- |
| stock24 | 11 | 15 | ble_wsf | 0040 / 1 |
| stock23 | 11 | 15 | ble_wsf | 0040 / 1 |
| Faceclaw38 | 11 | 15 | ble_wsf | 0040 / 1 |

All confirmed one GPIO IRQ59 entry, one rising edge, original ISR clear, one runtime event consumed, and one active CCB with handle 0040/peripheral role 1. Original event status/handle/role/address also matched DM action arguments. Original task Thread mode and stack remained; entry SP versus epilogue SP differed by 16 bytes, matching actual prologue. Fault, unsupported MMIO, and memory-policy violations were 0. Original main/initial assets were retained.

Observation ended **after DM connection-open action callbacks returned and immediately before the original pop epilogue**. It is not reported as completion of that pop or later controller commands. Startup command/reply counts were unchanged across enqueue, and runtime event was not disguised as Command Complete.

Reception begins only with peer enqueue. The new runner does not call guest functions, seed CPU registers, directly write NVIC pending, or write connection/security memory. IRQ arises from connected GPIO output. Observer reads ISR and DM action entry/epilogue and pauses the whole machine. Complete observer neutrality remains separately unverified.

Six standalone controls rerunning original `DmConnIdByHandle` against each native SRAM yielded 0040→1 and unregistered 0041→0. These are not new native runs. CCB creation was confirmed in original code, but encryption, authentication, and ATT admission have not yet been judged.

## Default path and failure controls

- Twenty-six new lifecycle unit checks passed, covering mask/clear/held level, duplicates, CS retry, abort, reset, NVIC59 wire, and more. Startup primer reads command getters of the same class to establish initial state by normal transactions. This prepares tests of the new runtime contract, not independent verification of startup command contents.
- Nineteen existing event/IOM unit checks passed on the new composite model.
- Stock24 default-off native control exactly matched previous CPU report, 53 candidate observations, and full SRAM. This controls only through existing initial main hold and does not guarantee all later behavior.
- Semantic audits rejected three synthetic negatives that changed PC seed, task owner, or connection handle while consistently updating JSON/log/hash. CLI also returned exit 1 for negative saved audits.
- Final frozen-tool saved audit is byte-identical to current stock24 audit. Before/after model and exact board/runtime/profile/observer/main/log/capture hashes are preserved.

Initial composite preparation was blocked because the preserved base constructor lacked newer GPU arguments. It was corrected to add only the GPIO owner after the actual last argument of existing source, without importing unrelated GPU arguments. A Renode launch with missing input after that preparation failure was also preserved and not counted as passing. Default-off schema 2 audit failed because the baseline SRAM invariant was omitted from prior metadata, although actual SRAM comparison was true. Metadata was corrected and only saved audit rerun, without restarting native.

The initial three natives were verified with 11 judgments; capture pin files were registered afterward as `import-after-initial-verification` following checks of original JSON/log agreement and existing verification. They are not portrayed as pre-execution pins. Subsequent saved audits separate schema 2 execution/semantic results and check all capture pins.

## Reproduction and next work

```sh
<private-python> tools/verify_runtime_event_gpio.py <simulator> <new-unit-output>

<private-python> tools/run_runtime_connection_m55.py <simulator> <new-output> --case stock24
<private-python> tools/run_runtime_connection_m55.py <simulator> <new-control-output> --case stock24 --control

<private-python> tools/run_runtime_connection_m55.py <simulator> <existing-output> \
  --case stock24 --audit-existing --audit-output <new-audit>
```

Execution assets are outside Git. Implementation extends existing peer/GPIO, runtime link, and optional runner; source differences replace only four explicit regions of the existing bundle. Frozen sources and unit/native/control/negative/lookup results are bundled in private `simulator/runtime-event-research-01/manifest.json`.

Next continue the same execution from the created connection through **H4 ACL/L2CAP/ATT write → registered EUS/TPL → time-setting final value**. Observe additional controller commands and flow control required by the original; do not arbitrarily ACK unsupported commands. Current support is one connection event, not a general controller or completed general CFW compatibility.

All 16 conditions, existing acceptance/status/evidence, and API 3/6 remain. E13 app data delivery is incomplete, so overall is 4/16=25.0%. No physical BLE/USB/UART, firmware installation, persistent write, or external publication occurred.
