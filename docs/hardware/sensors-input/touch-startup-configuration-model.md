# Touch configuration synchronization and input boundary

This records the configuration synchronization stage of `bw-0236`: lookup, configuration, status check, and reread were verified. Follow-up GPIO27 and event-query results are in a [separate record](touch-gpio-event-request.md). This is not completion of all touch initialization or full boot.

## Contract confirmed in the original

`tools/inspect_touch_startup_contract.py` executed unmodified original ARM fragments from pinned stock 2.4, stock 2.3, and Faceclaw38. It inspected limited fragments around external calls without substituting fake returns for separate callbacks/file I/O/logging. Original branches were not forced.

| Action | Original contract |
| --- | --- |
| Gesture configuration lookup | register 8, length 2, little-endian 16-bit threshold |
| Threshold validation | null/0 invalid, nonzero valid |
| Initialization target | exactly 800 (`0x0320`) |
| Configuration request | register 7 + two threshold low/high bytes |
| Configuration status query | three-byte response without rewriting pointer, header 7 / status 0 / trailer `0x17` |
| Initialization branch | skip configuration if lookup succeeds and threshold is 800; otherwise set 800 |

In stock 2.4, lookup decode is `0x4fbc68`, validator `0x4fbaf2`, configuration payload preparation `0x4fbb42`, response-frame check `0x4fbb6c`, response-status check `0x4fbbe0`, and initialization's 800 comparison `0x504f72`. Corresponding stock 2.3/CFW fragment locations are in the report.

66 isolated scenarios across three inputs and 90 checks including address/call arguments passed. These cover decode 0/1/800/65535, null/0/nonzero validation, low/high payload, invalid header/trailer/status, and natural branches for success/failure and 800/other threshold. Results are outside Git in `touch-startup-contract-01`.

Original I²C write wrapper concatenates register prefix and data in SRAM into a three-byte transmit buffer, so setting 800 is `07 20 03`. Native and unit tests also processed this request and status response through the existing FIFO engine.

## Explicit virtual initial state

New `BlackwallIomRegisterProbe` profile `touch-startup-config` requires explicit `initialGestureThreshold` in 0..65535. The option does not apply to other profiles.

- Initial 0: **test input assuming an unconfigured state**, not an actual factory/reset value.
- Initial 800: **test input assuming a state already matching the original target**, not a physical device reading.

The profile handles only previously verified version lookup, register 8 lookup, register 7 setting of a nonzero threshold, and pending-command status response `07 00 17`. Immediate success of supported configuration is an explicit untimed synthetic scenario. A new command cannot overwrite pending state and wrong-length reads cannot consume responses. The restriction requiring a new pointer for each read remains; arbitrary registers or touch events are not filled with 0.

Threshold storage is simulator-object RAM state. Whether this setting changes physical nonvolatile storage was not established. Model verification does not authorize actual I²C writes or installation. Original touch MCU execution, GPIO reset integration, physical completion delay, DFU, and event generation were not implemented. Although the touch package was obtained, this state model is not full touch MCU emulation.

## Native units and regression

Red was first confirmed with the existing constructor lacking profile/initial-value arguments (`touch-startup-red-01`). Then 41 checks each for initial 0 and 800, existing pointer-only 18 and version-only 25 passed, total 125. The first pre-extension 37-check run is preserved; final unit judgment is 41.

Checks cover original bus/FIFO delivery, little-endian lookup, configuration state changes, three-byte status frame, readback, duplicate pending command rejection, rejection of 0 configuration/unknown event register, wrong-length/version-response confusion, and selected initial-state restoration on reset.

Only a source comment changed after unit execution. Audit confirmed saved unit-model peer was byte-identical to the current candidate except that one comment line. Units were not repeated for the comment. Evidence: `touch-startup-unit-02-{zero,ready,pointer,version}`.

## Configuration flow performed by original main

`tools/touch-startup-candidate.json` is the initial-0 scenario; `tools/touch-startup-ready-candidate.json` initial 800. Existing pinned main/initial memory/observer/runtime remained; only peer component and explicit profile/initial value changed. Original PC, branches, returns, and delay loops were not skipped.

| Input | Gesture queries | Config writes | Status queries | Final threshold | Completed IOM5 transfers |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stock 2.4 initial 0 | 2 | 1 | 1 | 800 | 8 |
| Stock 2.3 initial 0 | 2 | 1 | 1 | 800 | 8 |
| Faceclaw38 initial 0 | 2 | 1 | 1 | 800 | 8 |
| Stock 2.4 initial 800 | 1 | 0 | 0 | 800 | 4 |

After original validator judged initial 0 invalid, original code wrote 800, checked status frame, and reread. At initial 800, it skipped setting/status check. Host did not inject success return or this branch. Eight transfers in initial-0 rows are version write/read 2 + gesture pointer/read 2 + config write/status read 2 + readback pointer/read 2.

All next strict boundaries are **GPIO27 status read `0x40010404`**: stock 2.4 PC=`0x49668c`, stock 2.3/CFW PC=`0x48a7a4`, CPU R0=27. This reaches input registration path after synchronization, not full registration return, event, or IRQ success. Actual GPIO27 level/polarity were not yet specified.

The original version-only profile control exactly matched existing CPU, instruction count, observations, and stop. Existing event prefix and UART0 bytes/eight IRQs were preserved in four successful scenarios. No claim that complete initial-0 error/configuration and initial-800 paths are identical. Results: `touch-startup-main-01`.

## Audit and remaining work

`touch-startup-verification-01/audit.py` passed 234 checks of original inputs, pinned component delta, manifest, actual logs, unit/regression, protocol counts, initial-value branches, next GPIO27 boundary, and off control. Like earlier audits it depends on saved source/model/logs/SHAs, not a replacement with the current builder. Python compile passed.

After this configuration stage, [GPIO27 sampling and event request](touch-gpio-event-request.md) were verified, closing bw236's limited model work. Actual edge/IRQ, event data, and full touch support remain incomplete. Do not guess physical level or idle polarity and treat the whole GPIO bank as known. Overall goals including possible screen output, normal font-bank, app loop, web-integrated installation, and physical recovery remain incomplete; product fulfillment remains 13/29 (44.8%).
