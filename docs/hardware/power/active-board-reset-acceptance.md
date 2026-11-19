# Virtual Reset of an Active Board and Original App Return

bw-0484. **E06 was completed.** A virtual NVIC reset was triggered in the active UI state verified by E05 for stock 2.4, stock 2.3, and Faceclaw38, and original main re-entry → service reinitialization → UI, continuous frames, and task wait/resume return were verified. Overall conditions are **14/16=87.5%**; denominator and acceptance wording remain unchanged.

Virtual NVIC AIRCR `0xe000ed0c←0x05fa0004` is an explicit external device input. The host does not set PC/SP/TCB or modify original code/vectors. This is not described as a test in which original firmware itself calls reset. It is not certification of Boot ROM/bootloader or physical Apollo reset/power retention.

## Actual restart of three originals

| Original | Reset count | Completed-frame counter | After first reboot screen | Post-reboot wait → same task callback |
| --- | --- | --- | ---: | ---: |
| Stock 2.4 | 0→1→1 | 7→0→7 | 100.088 ms, 5 frames | 4.817 ms |
| Stock 2.3 | 0→1→1 | 7→0→7 | 100.171 ms, 5 frames | 5.035 ms |
| Faceclaw38 | 0→1→1 | 7→0→7 | 100.293 ms, 5 frames | 5.033 ms |

Each progression denotes before reset → original reset entry → after reinitialization. Times are virtual, not physical FPS/latency comparisons. All three re-entered original vector PC/SP and VTOR `0x438000` and restarted without an additional reset. Faceclaw follows the same stock UI fallback path as before.

After reboot, original app initialization type 2 callback return, receive wait list of the actual empty UI queue, later type 4 callback in the same TCB, and five completed frames were confirmed. In both cold/warm intervals guard, CFSR, HFSR, memory protection, functional-cache violations, and GPU rejection/fault were 0; there was no CPU debugger halt.

## Reset domains and observations

| Domain | Policy in this virtual profile | Actual check |
| --- | --- | --- |
| CPU/NVIC | Re-enter original vector, initialize NVIC/BASEPRI | Original PC/SP/VTOR, one reset, BASEPRI 0 |
| Functional cache | Reset IC/DC enabled and initialization history | enabled→disabled→enabled, initialized lines 2048→0→2048 |
| GPU capture/command | Reset consumer, IRQ, submissions, capture state | Completion counter 7→0→7, entry capture bytes 0, new original submissions/frames |
| IMU/GAF/FIFO | Reset transport, configuration, service state | phase disabled→unselected→disabled, FIFO ready true→false→true |
| Controller/UART/touch | Reset virtual session and consumption state | peer Complete/59→Unreleased/0→Complete/59, UART RX 36→0→36, touch 1→0→1 |
| ITCM | Preserve backing and guest-written provenance | Full ITCM hash and 24 written bytes preserved at entry |
| NOR KV/LittleFS | Preserve backing, reset transfer state | Each full backing hash matches before reset/at entry; program/erase/PIO idle at request |
| SRAM | Preserve backing, allow original activity and startup rewrites | Full SRAM collected before reset/at entry; bit-exact preservation between them is not claimed |
| Other existing peripherals | Retain existing registered Reset/owner-helper policies | Compiled source and existing [domain audit](reset-domain-acceptance-audit.md); not every possible non-idle combination tested |

GPU counter/capture initialization is internal emulator state, not a claim that physical optical display immediately turns black at reset. Source frames after new submissions were separately verified.

Original activity can occur between asynchronous request and entry. Changed SRAM bytes before/after were 219 for stock 2.4, 13 for stock 2.3, and 0 for Faceclaw. These are not interpreted as pure reset loss or exact retention measurement for all SRAM. Pinned Renode MappedMemory.Reset no-op policy and existing synthetic-cookie verification remain; original code was subsequently confirmed reinitializing globals, stack, and task state and returning to the app. This is not a physical SRAM-retention guarantee.

## Changes connecting existing components

The active-screen model lacked previous reset memory-read protection reconnection and cache initialization fixes. bw419 `29daafce…` memory policy and bw420 `5564e889…` system-control were reused by pinned SHA. Existing protection was not disabled and main padding/ITCM provenance checks were not weakened.

Existing reset-aware NVIC and reset-entry observer were also reused. The observer follows bw426 order, exposing completion after machine Pause finishes. When returning to startup 10 MIPS input at original reset entry, general registers, SRAM, virtual time, and device state were preserved. Existing 167 MIPS profile was subsequently used on original HP/UI path. This is an execution-rate input, not a bypass of guest clock branches or actual performance.

Original main is unchanged. During first boot of the new configuration, six SRAM snapshots before/after input, before/after UART reply, app request, and UI dispatch are byte-exact against each E05 baseline.

## Power boundary found and cause confirmed

The first stock 2.4 run succeeded through reset, vector, service reinitialization, and new UART input, but strictly stopped at `0x40021004` before UI dispatch. An existing post-stop exporter was attached for separate collection instead of guessing the owner from address alone.

- Request `0x8e20` → proposed `0x8f20`, XOR `0x100`: IOM7 resumption.
- IOM7 was off-requested/request 0/status `0x100`; IOM4 in the same HCPC was on/request=status `0x20`.
- Buck was active, consistent with the existing shared-IOM local-gate/reopen contract.

Model and final warm SRAM were exact before/after diagnosis; general registers, time, and SRAM also matched before/after reads inside the exporter. Failed and diagnostic runs were preserved.

Existing optional composition and board profile in `iom_shared_power_model.py` were applied unchanged. Pinned power-class SHA `5221ccf2…` and branches were checked, explicitly specifying only five IOM2/4/5/6/7 owners. Host does not change runtime phase or add guest status polls. The unverified physical accuracy scope of shared power remains as in the [existing contract](iom-shared-power-lifecycle.md).

Six stock 2.4 warm input/ACK/app-request/display-send SRAM snapshots were also exact before/after applying the profile. Original behavior before the observed power boundary was not changed to bypass it.

## Verification tools and counterexamples

`run_active_board_reset.py` uses E05 pinned inputs and reruns the same original UI/frame phase after reset. Output is separated under `exports/restart/` to avoid overwriting first-boot material. `audit_active_reset_acceptance.py` assesses all three saved cases without rebuilding the model or executing ARM.

Five new native runs comprised one failure, one diagnostic, and three successes. Absence of all five owned containers was confirmed in actual Docker listings. Thirteen Python audit dependencies were frozen; all three cases and integrated audit ran from `/tmp` with empty PYTHONPATH. The ordinary integrated audit was also byte-exact with the frozen report.

Saved-material counterexamples removing reset count, retaining stale GPU state at entry, and losing preserved KV hash each pass execution-configuration integrity but fail semantic checks. If one case fails, E06 as a whole fails even if the other two pass. These counterexamples are not new guest runs.

The initial host audit mistook the 2.4 callback `pc` for return time and did not distinguish older families' `family-screen.bin`/`family-boot.json` formats. It was explicitly normalized to check the actual return-observation row for 2.4 and return-time snapshot plus pinned observer configuration for older families. Saved audit was corrected while original runs were preserved. Failed reports and inputs also remain.

## Next goal

The earlier first-screen auxiliary checklist M3's unconnected frame type 3 readiness was replaced by E05 natural main, original UI/readiness path, and actual render/packing evidence. M3 is also linked to that evidence and marked complete. The first-screen auxiliary checklist is 6/6 and is not double-counted in the overall 16 conditions.

**E06 complete, 14/16=87.5%.** Remaining conditions are E11 additional virtual input → original state/screen change and E12 sensor samples → FIFO/IRQ → original consumption. Functional sensor/GPU assumptions and physical-unverified boundaries remain. No physical access, flash/OTA/MRAM writes, subagent calls, or GitHub publication occurred.

Pinned originals, SRAM, frames, logs, and tools remain outside Git in `simulator/active-board-reset-{native-01,power-native-01,shared-native-01}`, `active-reset-{frozen-audit-01,acceptance-01,negatives-01}`, and `active-reset-manifest.json`.
