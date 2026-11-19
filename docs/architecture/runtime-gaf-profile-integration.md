# Integrating the Communication Runtime with a Pinned GAF Profile

bw378. This connected separate E05/E14 execution foundations. In the same original ARM main reset and device BLE session, execution advances through the existing 153-byte GAF getter and 225-byte configuration storage. Original branches, returns, and TCB/SP were not forced, and no service-success response was added. **GAF calculation, completed normal initialization, and long-duration communication-failure handling remain incomplete.**

Optional `--gaf-profile` was added to existing `runtime_event_models.py` and `run_runtime_connection_m55.py`. Instead of importing the entire in-progress IMU file, it reuses the frozen component SHA `3ddefc4c…` verified in bw353 and the same plan's published-defaults 153 bytes, configuration, and explicit trim 0x85. This trim is not an actual device value. Actual reset values, computational accuracy, and physical timing are unverified. With the explicit option off, the previous model combination remains.

Other parts of the synthetic model are preserved byte-for-byte. Legacy IMU component SHA `fabd6fd5…` and candidate SHA are checked, and only one section is replaced. Source/fixture/plan hashes are pinned in the capture. Saved audits recalculate the actual IMU component hash from captured strict.cs and compare it with the original run's fixture/metadata. Past captures are not regenerated using the current builder.

| Result | stock24 | stock23 | Faceclaw38 |
| --- | ---: | ---: | ---: |
| Device → time setting → immediate-close regression | 37 checks passed | 37 passed | 37 passed |
| GAF fields/reads during long wait | 41 / 153 bytes | 41 / 153 bytes | 41 / 153 bytes |
| Actual original configuration writes | 225 bytes | 225 bytes | 225 bytes |
| Comparison with existing natural-main write history/values | Exact | Exact | Exact |
| Virtual time to next boundary in long wait | 171.3286 ms | 171.3401 ms | 171.2500 ms |
| Separate observation of transmitted word immediately before stop | Not collected | 7c000402 | 7c000402 |

Times are pinned virtual time after long wait begins at return from local RTC consumption, not physical performance comparisons. The disconnect scheduled at 1000 ms did not occur before the stop in any case. Therefore native verification for the three long tests is retained as **passed=false**. A passed history comparison verifies evidence up to the next integrated boundary, not service completion or E14 success.

The stop is at sensor_hub IOM4 CMD 0x40054120. For stock23/CFW, original HAL `ldr r1,[r4]` → FIFO write → pointer+4 → CMD write was confirmed in original code, and actual R1 and the transmit buffer's four bytes were both 7c000402. Stock24 had the same 225-byte history and was confirmed to the existing HAL boundary, but initial capture did not separately export general registers, so direct observation of its transmitted word is not counted.

The GAF snapshot's existing service completion 2 represents two earlier initialization services. It does not mean calculation for the new GAF request ID 2 completed. After executing the GAF getter for 41 fields/153 bytes, one trim read, and 225 configuration writes, execution stopped strictly at the first unsupported request. Next request 4, mask/disable and calmag processing, and Sensor initialization return remain incomplete. Do not confuse initial service control with GAF calculation effects.

The control reaching main hold with the selected GAF component matched the existing baseline exactly in complete CPU report, 53 observation points/all events, and all SRAM. The first communication prototype also passed 36 checks, but the builder did not put GAF selection in connection-profile, so the new diagnostic snapshot was missing. That control/prototype was retained. A new stock24 capture with corrected metadata ran, and model/board were separately confirmed byte-identical to the prototype. Thereafter the three originals were verified with 37 checks through the declared GAF profile and actual initial snapshot.

New native runs comprised one control, one missing-diagnostic prototype, three formal immediate-disconnect runs, and three long-wait runs. Do not cover over the unsupported failure of the three long waits as success. The existing 4,017 IMU unit checks were reused as pinned results for the same frozen component. Six new composition checks verified preservation of other components, rejection of corrupted/duplicate/missing source, and fixture declaration. No new register-specific standalone tool was added as a product feature.

Saved regression audits of formal/existing communication captures included 440 positive assessments and reproduction of failure judgments for three new unsupported captures. The frozen auditor was byte-exact across new normal, new unsupported, and existing E13 captures. Three negative cases mutating the actual compiled IMU, observation fixture, or declared trim while consistently updating JSON/log/input hashes were rejected by `pinned_gaf_profile`. The CLI also returned exit 1 for negative cases. These were not three new guest executions.

The older IMU boundary previously encountered at 1.2286 ms in long waits was resolved. The result is that communication and the next GAF service boundary in natural main are connected in the same original execution. **Overall 5/16 = 31.25% (displayed 31.2%) and API 3/6 remain unchanged.** Full E05/E14, natural UI, and opposite-temple/case runtime delivery remain incomplete. There was no physical BLE/USB/UART, flash/OTA, persistent write, or external publication.

Next, distinguish request recording, RMW, trigger, pending, completion/error, mask/disable, and supported computation effects in the already analyzed [GAF on-demand contract](../hardware/sensors-input/imu-gaf-service-contract.md). Do not return ready alone and claim normal computation. Accesses requiring unsupported derived RAM results remain strict. Focus on this common service dependency instead of repeating variants of the same legacy getter/long delay.

```sh
<private-python> tools/run_runtime_connection_m55.py <simulator> <new-output> \
  --case stock24 --att-time --disconnect-reason 0x13 --gaf-profile
```

`--disconnect-delay-ms 1000` is a research failure scenario reproducing the current gap in next GAF service support. Saved audits use `--audit-existing --audit-output <new-audit>`. Initial prototype/control captures lacking metadata are reaudited under their historical default assessment with the GAF flag omitted and distinguished from new declarative GAF captures. Required pinned images, templates, source manifest, and fixtures are retained outside Git.

Evidence: `private:simulator/runtime-gaf-research-01/{manifest.json,boundary-verification.json,composition-verification.json,hold-control-comparison.json}`, `runtime-gaf-saved-audit-01/report.json`. Proprietary ARM/SRAM are not included in the repository.
