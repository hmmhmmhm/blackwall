# Support Boundary for GAF Request Control and Calculation Results

bw379, partial E05/E12/E14 work. The optional research profile `--gaf-on-demand-control` was added while retaining the existing pinned GAF model. Original ARM instructions, branches, returns, and TCB/SP are unchanged. **Request/trigger/pending control was verified; GAF calculation and completion of normal initialization were not implemented.**

Default `--gaf-profile` retains the earlier SHA `3ddefc4c` strict behavior. Only research mode composes the verified connection and `renode-gaf-ondemand.cs` into that pinned source. Composed SHA is `c2af9898`, fragment SHA `4c7afaae`. Other in-progress IMU changes were not imported wholesale. Model, source, profile hashes, and actual compiled component are compared in saved audits.

| Stage | Virtual device behavior | Verified scope |
| --- | --- | --- |
| Preparation | Requires existing two initial services, getter 153 bytes, one trim, and 225-byte configuration | Unit and 3 originals |
| Request | Store ID 2 or 4 in SRAM 0004 | Three originals use ID 2; ID 4 unit-tested only |
| Control | Clear A272 bit 5, set 2A bit 6, set 73 bit 5 | Actual 3 reads/3 writes/1 trigger in all three originals |
| Pending | Supply idle byte 0 during the selected virtual observation interval | Original ARM busy polling 7 times in 10 ms mode |
| Result needed | Strictly reject status/result requests after observation interval because completion validity cannot be established | Three originals, 0 completed calculations |

The 1 ms/10 ms observation windows are explicit simulator inputs, not physical GAF latency. `CalculationSupported=false` and `CompletedCalculations=0` are separately recorded in the profile and actual snapshot. End of an observation window is not calculation completion. No completion state is returned; pending/result remain unsupported. Derived RAM reads are not allowed to use 0 as a calculation result.

Actual history across the three originals was `request:2|a272:1f|2a:cb|73:e9`, confirming request RAM byte 2, one request, three RMW writes, and one trigger. GAF 225-byte history/values are exact against prior original runs; two earlier initial service completions do not mean the new request 2 completed. After existing control, the gap was made explicit at original Sensor A297 status selection (`7ca297`). The long native verification remains preserved as passed=false, distinct from its checkpoint confirming the control path.

In 1 ms mode the first status access occurred after the observation window. This is not claimed as busy-loop execution. A separately contracted 10 ms mode verified the original ARM actually reading the busy byte and polling seven times. Values were not increased to create normal completion, nor were the same variants repeated. Actual firmware timeout, normal request 2 → 4 sequence, and normal initialization return remain unverified.

Initial hold's full CPU/report, 53 observation points/all events, and full SRAM were exact against the existing baseline. Time/immediate-close control with the research component selected passed 38 judgments. Three long original scenarios passed existing communications/app phases and capability declaration, then ended at the unsupported result boundary. New native runs were hold 1, three long originals, busy 1, and immediate close 1; all are private simulator runs unrelated to physical devices.

The 156 unit checks use IDs 2/4, different mask states, and original 225-byte configuration to check prerequisites, rejection of wrong order/bit changes/duplicate requests, surrounding RAM preservation, pending, reset cancellation, and unsupported result access. Frozen-source unit results have identical JSON values. Byte comparison failed because top-level key order differed from the original report; this is not a difference in calculation or check results. Byte-exact checks for native capture audits remain. Unit tests do not verify original ARM or physical devices.

In an initial timing test, after advancing a 100 µs observation interval by 99 µs + 2 µs, machine time read in the callback was recorded as 101 µs. An inspector interpreting this as the exact event deadline failed. Logical `DeadlineAt` and callback processing time `EndedObservedAt` were separated; both 1 µs interval boundary checks and larger-step observation-range checks passed. With larger steps, observed time may equal the deadline or occur later within the observation range. Three initial failures were preserved; the uncertainty interval is not hidden or generalized to physical timing verification.

Five negatives tampering with declared calculation support, observed calculation completion, timing metadata, and control checkpoint fake completion/deadline along with JSON/log/hash were rejected. The CLI also rejects modes outside audit scope or different observation windows. Historical captures are checked against their saved model/inputs/logs and are not retroactively made dependent on the new builder.

Existing 16 acceptance/status/evidence items and API 3/6 remain. Overall is 5/16=31.25% (displayed 31.2%). GAF mathematical results, sensor fusion, normal main initialization, full display, and long BLE timeout remain incomplete. No physical BLE/USB/UART, flash/OTA, permanent writes, or external publication occurred.

Next, narrow the RAM actually consumed by the driver after requests 2/4 and the calculation effects contract from existing source and complete setter evidence. Do not confuse control-stage completion with actual calculation completion; state unsupported results explicitly. Do not expand the same trigger/pending or delay-value tests again.

```sh
<private-python> tools/run_runtime_connection_m55.py <simulator> <new-output> \
  --case stock24 --att-time --disconnect-reason 0x13 --disconnect-delay-ms 1000 \
  --gaf-profile --gaf-on-demand-control
```

This command is a research failure scenario exposing the current calculation-result support gap. Select the busy path with `--gaf-control-window-us 10000`. Omit `--disconnect-delay-ms` for normal time/immediate-close regression. Private source, logs, checks, and frozen tools are preserved in `gaf-on-demand-research-01`; proprietary ARM/SRAM remain outside Git.
