# Delayed Disconnect During Frozen Sensor Execution

bw400. This experiment combined an explicit EDMP execution-freeze fault with a virtual BLE controller disconnect event during stock 2.4 ARM main reset execution. It does not assume successful normal GAF computation or completed full initialization.

## Inputs and execution path

At the full-machine pause after the existing runtime ATT time setup, only the three owning-PC observation callbacks verified by bw399 are stopped. The model's complete text matches the bw399 pinned scoped model, and the original main image is the same. The default model and existing nominal audit are unchanged.

After an immediate-disconnect control, a one-shot timer injects the controller event at virtual time 1000 ms. It uses the original GPIO/IRQ → SPI/H4 → WSF task → disconnect handling → original return path. It does not set PC, R0, TCB, or SP, or skip original waits or branches. Sensor request 2 remains busy, with zero calculations and completions.

## Distinguishing the RTC audits

The existing `disconnect_rtc_preserved` check requires the time to start at `22:13:20`. The delayed 1000 ms run actually advances from `22:13:20.04` to `22:13:21.04`, so it fails that check. The first failure report is preserved.

A separate combined audit checks that RTC commit remains 1, pending remains false, and error remains none, while the difference between elapsed RTC time and total elapsed virtual time is less than the display precision of 10 ms. The existing nominal report remains false. The `pinned_gaf_profile` failure, which prevents treating the combined model as nominal GAF, is also preserved. All other existing peer checks must pass.

## Tools and limitations

There were three new original ARM executions. All three reached the original disconnect return address `0x4d4044`.

| Input | Sensor busy reads | Virtual elapsed time during disconnect interval | Original app notification |
| --- | ---: | ---: | --- |
| Immediate, reason `0x13` | 0 | 3.0477 ms | `010028000000400013` |
| After 1000 ms, reason `0x13` | 926 | 1003.1794 ms | `010028000000400013` |
| After 1000 ms, reason `0x08` | 926 | 1003.1794 ms | `010028000000400008` |

Each passed 37 existing checks and 14 combined checks. Delayed runs include a separate elapsed-time check in place of the existing same-second RTC check. Do not report this as a full pass of the existing nominal audit. The checks confirmed GPIO deassertion, CCB deactivation, original task/stack, preserved RTC commit, and zero guard/CPU faults. The immediate control occurs before the sensor request; both delayed runs have request 2/trigger 1, busy 926, calculations 0, and completions 0.

Three saved captures were reaudited and three semantic mutations were tested: false calculation success, an extra one-second RTC error, and inconsistent delay metadata. Each mutation was rejected even when logs and hashes were regenerated consistently. Fourteen progress-management checks also passed.

```sh
<private-python> <trusted-local-wrapper> tools/probe_frozen_peer_disconnect.py \
  <simulator> <new-capture> --delay-ms 1000 --reason 0x13

<private-python> <trusted-local-wrapper> tools/probe_frozen_peer_disconnect.py \
  <simulator> <saved-capture> --audit-existing --audit-output <new-audit>
```

`0x08` is the controller-reported connection-timeout reason. Injecting this event does not establish an actual RF timeout or expiration of the original host's timeout. Reconnection, normal GAF calculation, normal full boot, and integrated display remain unverified. This is not counted as full E14 completion; overall progress remains 7/16 (43.8%) and API progress 3/6.

No physical-device access, firmware installation, subagent, or external publication occurred. Private material is retained in `frozen-peer-disconnect-native-01` and `frozen-peer-disconnect-research-01`.
