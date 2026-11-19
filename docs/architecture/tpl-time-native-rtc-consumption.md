# Original BLE Task Time-Message Consumption and RTC Application

bw372, E13/E05. The TPL time-setting message from the [bw371 isolated contract](tpl-service-app-terminal-contract.md) was executed on the existing M55 board. **On stock 2.4/2.3/Faceclaw 38, the original `ble_msgrx` task consumed the queue, applied time to the RTC, and returned to its original caller.** Input remained a TPL API diagnostic, not actual ATT device input or completed natural main initialization.

## Existing model and execution path

The existing `BlackwallRtcAdapter` and pinned RTC engine were used unchanged. Model source, original main, and initial SRAM/ITCM match the existing baseline byte-for-byte. The only board difference is selecting the existing `halLowUpperWrites` profile true instead of false. This profile is a virtual transaction assumption following HAL LOW → UP write order and date/BCD/weekday checks. It does not establish actual silicon write order, latency, or oscillator accuracy.

The `tpl-service-time` scenario was added to existing `run_sync_transport_m55.py`. After reaching the existing normal hold from main reset, a serial TPL API caller is inserted in Sensor context. The message uses service 80, bit 5=0, command 80, nested field 128, time 1700000000, and auxiliary value 16. Original TPL/registered callbacks create the actual receive queue and signal the task event.

The test caller does not call the consumer, protobuf decoder, clock helper, or RTC-setting functions. Nor does the host set UI/BLE task PC, TCB, SP, or priority. The observer watches TPL entry, original consumer entry, clock-application return, and consumer-function return to its original caller. It pauses the whole machine at the last point. Complete noninterference of observation hooks remains unverified.

## Results for three originals

| Target | New native checks | Latest saved audit | RTC commit | Virtual RTC date |
| --- | ---: | ---: | ---: | --- |
| stock24 | 15 | 18 | 1 | 2023-11-14T22:13:20.03 |
| stock23 | 15 | 18 | 1 | 2023-11-14T22:13:20.03 |
| Faceclaw38 | 15 | 18 | 1 | 2023-11-14T22:13:20.03 |

Each execution retained the original `ble_msgrx` TCB, Thread mode, and original stack range. SP at consumer entry and return to the original caller matched, and the actual queue was empty. Five app-state bytes matched input; RTC had commit 1, writes 5, pending false, and LastError none. The date matched the seconds value independently calculated from input Unix time. The final 0.03 seconds is virtual elapsed execution, not a physical-device precision measurement. Faults, unsupported accesses, and memory-policy violations were zero.

Three checks added in the saved audit cover three permitted test-caller calls, declaration of the RTC write profile, and natural preemption order. Calls declared for the caller are TPL entry and existing queue new/get only. The latter two calls are after TPL return but **had not yet executed in this capture**. With input-return marker 0, priority-48 BLE task preempted priority-41 Sensor; time application and consumer return completed first. BLE consumption was not produced by forcing a yield using a synthetic wait queue. TPL input-caller return itself had not yet been verified at this point.

The bw371 0x40004800 unmapped access was a boundary of an isolated fixture that did not use the existing RTC model. This dependency was resolved by the same original function performing actual RTC transactions on the existing board/profile. No arbitrary read value or helper-success return was injected.

## Verification and reproduction

```sh
<private-python> tools/run_sync_transport_m55.py <simulator> <new-output> \
  --case stock24 --scenario tpl-service-time

<private-python> tools/run_sync_transport_m55.py <simulator> <existing-output> \
  --case stock24 --scenario tpl-service-time \
  --audit-existing --audit-output <new-audit>
```

There were three new native runs. Saved audits checking JSON/log/capture input hashes had 18 assessments each; frozen-tool stock24 audit matched current audit bytes. Three synthetic negatives separately mutating RTC date, original return task, and queue remainder while consistently updating JSON/log/hash were rejected by their semantic checks. Negative audits are not new firmware executions.

Nine existing transmit, RX/UI, and TPL-transmit captures were reaudited with the current checker, passing 213 assessments. Existing inputs were not run in a new guest. The first audit attempt failed on import because system Python lacked Unicorn; it was performed using the approved simulator venv instead. Do not mix this with a native execution failure.

Implementation comprises `tpl_service_native.py`, optional observer, and scenario branch in the existing runner. Input main/SRAM and source contracts are bound to the prior manifest; exact model/board/harness/runtime/log of the capture are retained. Results, frozen source, and hashes are in `private:simulator/tpl-time-research-01/manifest.json`. Proprietary originals/SRAM are outside Git.

## Next integration boundary

The app endpoint for this scenario was specified as **original-task time-state update, exact virtual RTC commit, empty queue, and consumer return to its original caller**. Since it starts at TPL API rather than actual controller/ATT input, E13 remains partial. BLE connection/security, no-connection control, error/delay, per-peer roles, and virtual-time limit also remain.

Next is a minimal contract connecting controller connection-complete event → original HCI/DM/valid CCB → ATT → EUS/TPL → this endpoint in one execution. Normal BLE task preemption was confirmed, but whether controller input can reach it before the natural GAF barrier needs separate validation. If blocked, switch to E05 normal service effects/completion. Do not count bypassing that barrier with an API caller as E05/E13 completion.

All 16 criteria, acceptance/status/evidence, and API checklist remain unchanged. Overall remains 4/16 = 25.0%, API 3/6. No physical BLE/USB/UART, installation, persistent write, or external publication occurred.
