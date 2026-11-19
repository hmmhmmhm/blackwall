# From Device ATT Input to Original Time Setting

bw375, E13 local-time-setting scenario. The pre-execution contract is recorded in `private:simulator/runtime-att-research-01/acceptance-contract.json`. Plans in this document are not pass evidence.

## Pre-verification contract

Run original stock24/stock23/Faceclaw38 from ARM main reset to the existing hold. Then inject a virtual controller connection event, and let original IRQ/SPI/HCI/ATT/EUS/TPL/ble_msgrx process the time setting. No API caller or forced guest PC/TCB/SP or connection/security bytes are used. Existing observation hooks and explicit initialization profiles are retained.

The virtual-time budget is **20,000 ms**, measured once from the pause immediately before connection-event enqueue through return to the original consumer function's caller. The 45-second host watchdog is separate process protection and does not substitute for virtual-time evidence. Earlier native-05 lacked instrumentation, so this contract is not applied retroactively. New acceptance-native-01 was run to verify time limit and peer roles/output in the same capture. This budget is not a physical-device latency target or performance measurement.

The phone is virtual central handle 0x40; after responding to MTU 247 requested by the original, it sends an ATT Write Command. It uses service 0x80/command 128/nested field 128, timestamp 1700000000/raw byte 16. Deterministic eight-byte Rand, RSSI -42, and remote features 0x01 are explicit fixtures, not actual iPhone/controller capabilities or entropy. Unknown controller commands do not receive automatic success responses.

Opposite temple/case retain existing startup-fixture roles. When local time application completes, two original-generated messages (kind 4 and kind 1) wait in the transmit queue. Thus do not claim the opposite temple has no involvement. This scenario ends at local RTC commit, empty app queue, and consumer return; outbound delivery/opposite-side consumption remain unverified. Case runtime commands were not required on this observed path. Full original execution of both sides/case or OTA was not validated.

Normal assessment requires original BLE task/stack/Thread mode, exact five-byte time state, RTC commit 1, date to seconds, input/consumption/application/return each 1, device inputs 3, IRQ 7, clear/pending deassertion, zero faults/unsupported accesses, virtual-time limit, and two pending sync messages. The negative control changes only target to 0x844 and requires original permission error 3, input/consumption/application 0, RTC commit 0, and no sync increase. Feature off is compared with existing main hold, observation, and full SRAM.

An early iteration misread an active Rand packet and not-yet-popped TX ring head as two Rand commands. The normal path has one Rand. Earlier failed captures are retained and not overwritten as successful reruns.

## Results and acceptance assessment

| Target | Native/saved checks | Virtual time from connection input to consumer return | RTC commit | Original app queue / outbound sync queue |
| --- | ---: | ---: | ---: | --- |
| stock24 | 25 | 54.6497 ms | 1 | 0 / 2 |
| stock23 | 25 | 53.6561 ms | 1 | 0 / 2 |
| Faceclaw38 | 25 | 53.4938 ms | 1 | 0 / 2 |
| stock24 read-only target | 22 | Within 20-second budget | 0 | No increase / 0 |

Time units are checked at the pinned Renode rate of 1,000,000 ticks/ms. Do not change the denominator so a timeout passes. For the three originals, input/consumption/application/return were each 1; app-state timestamp/raw byte matched; RTC date was 2023-11-14T22:13:20.04, pending false, error none. Original task/stack/Thread mode and connection/MTU/runtime controller counters were verified. Faults, unsupported accesses, and memory-policy violations were zero.

The three normal captures are in `private:simulator/runtime-att-acceptance-native-01/{stock24,stock23,cfw}`; the permission negative is in `runtime-att-acceptance-readonly-01/stock24`. Twenty-four runtime lifecycle unit checks from the same model source reused existing `runtime-att-unit-01` results. The original execution model and unit-test strict.cs were confirmed byte-identical; the startup primer uses the same class's command getter, so it is not counted as an independent oracle for initial command content.

One feature-off native run using the current model was exact against existing hold in complete report, CPU, 53 observation points/all events, and all SRAM. This control covers only initial hold; it does not prove complete noninterference of the active runtime observer.

The three new normal, one negative, and one default-off capture were reaudited and matched original assessment JSON bytes. The three earlier native-05 normal captures were also reaudited with the current auditor, each passing 23 checks. Stock24's initial connection-only audit failure was retained and distinguished from a later phase-aware audit success. Final-auditor and frozen-source stock24 saved audits also matched bytes. The final auditor's additional change checks pinned ticks/ms; guest execution code and model were not changed again.

Six synthetic mutations consistently updating result JSON/log/hash—timeout, zero unit, wrong positive unit, wrong RTC date, original consumer task, and outbound-queue remainder—were rejected by the corresponding semantic checks. The CLI also returned exit 1 for the timeout audit. These were not six new guest executions. Proprietary main/SRAM/diagnostic logs remain outside Git.

E13 acceptance for declared per-peer roles and virtual transport → original protocol/task → app behavior was satisfied in this same execution. E05 completion is not an E13 prerequisite; incomplete natural GAF initialization remains disclosed. This assessment covers the local time-setting scenario, not general support for every other peer message or opposite-temple/case runtime behavior. Existing acceptance criteria, denominator, and statuses outside E13 were retained. E01–04 and E13 yield **5/16 = 31.25%** (displayed 31.2%).

## Reproduction and next boundary

```sh
<private-python> tools/run_runtime_connection_m55.py <simulator> <new-private-output> \
  --case stock24 --att-time

<private-python> tools/run_runtime_connection_m55.py <simulator> <existing-private-output> \
  --case stock24 --att-time --audit-existing --audit-output <new-private-audit>
```

Use `--att-readonly-control` for the permission control and `--control` for feature off. Do not combine `--control` and `--att-time`. New runs require saved stock images, source manifest, and template, and check SHA of pinned model/inputs. They do not automatically support every new command order in arbitrary CFW.

Next is **E14 original state/timeout/cleanup and reconnection or explicit failure after disconnect, delay, and malformed messages** in the same connection runner. First define input timing, virtual time, and terminal oracle; expand only precisely supported messages in the existing model. Do not count one permission rejection as full E14 completion. Natural GAF/E05, full display/E09, and actual peer-sync delivery remain incomplete. No physical BLE/USB/UART, flash/OTA/persistent write, or external publication occurred.

Hashes of inputs, executions, final audits, unit tests, mutation controls, and frozen tools, plus the acceptance assessment, are retained in `private:simulator/runtime-att-research-01/manifest.json`.
