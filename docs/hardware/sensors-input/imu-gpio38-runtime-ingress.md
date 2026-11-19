# Original M55 entry through GPIO38 IRQ57

bw465. **Main reset → existing hold → GPIO38 rising edge → IRQ57 → registered callback → original clear → return to interrupted original code** was verified for all three originals. This advances the [earlier isolated gate/callback analysis](imu-fifo-gate-and-pin-contract.md) to device input on actual Renode M55. Normal GAF, FIFO sample consumption, and natural screen remain incomplete; overall 10/16=62.5%.

## Verified configuration and limited model

All three existing original captures had PINCFG38 (`0x40010098`)=`0x93` and bank1 enable=`0x40`. The pinned Ambiq header commit `61b293a49db34030c545f99101f7ebf6a3050314`'s eIntDir bits 7:6 and LO2HI=2 were rechecked, as were file SHA256/Git blob. New native runs also confirmed the same pad, mask, and NVIC57 enable.

Default-off `runtimePin38`, `TrySetPin38`, and `IRQ38` were added to existing `BlackwallGpioInterruptIdle`. A rising edge from virtual initial low latches pending; bank1 mask determines IRQ57 output. Original W1C clears only pin38 pending. Held-high/falling creates no new event, and reset initializes virtual low and pending/counter. This low or latency is not interpreted as physical idle/timing.

Existing 117/27 state, IRQ, and clear were kept separate, and default IRQ assignment preserved. Public core changes are confined to the GPIO class; remaining source bytes match baseline. No new general GPIO emulator or arbitrary ready behavior was added. This follows the existing-model reuse approach in the [implementation plan](imu-gpio38-runtime-plan.md).

## Actual original execution results

| Item | Stock 2.4 | Stock 2.3 / Faceclaw |
| --- | --- | --- |
| IRQ57 ISR | 0x4fc90e | 0x557536 |
| Registered callback | 0x4c615e | 0x4baaa2 |
| Actual ISR/callback | Once each | Once each |
| IRQ context | IPSR73 | IPSR73 |
| Clear | bank1 bit 6 | Same |
| Exception return | Original getter/Thread mode | Same |

Original firmware and board main reset execution were used; the host did not specify CPU PC/general registers/TCB/SP or gate/timestamp. No bus/RTOS leaf ABI was replaced. After holding in the existing runner, only the model's GPIO38 edge was supplied.

Pre-injection SRAM was exact against each image's existing baseline. Full SRAM, R0–R15, and virtual time were also unchanged immediately before/after injection. Actual ISR/registered callback/return point IPSR73, original clear, and pending/IRQ release were confirmed before exception return to the original getter. R0–R15 after return were also exact against pre-injection. This verifies a fixed input on the IRQ path, not absence of effects across all observers/inputs. It does not claim all SRAM was unchanged after IRQ execution.

Gate and timestamp remained 0 in each run, so the callback correctly returned along the initial gate-off path. No message 2, FIFO read, or sample processing resulted. The gate was not opened and GAF ready was not manipulated. CFSR/HFSR, memory violations, and 17 strict guards were all 0.

## Controls and regression

- Five new original M55 runs: three normal-edge images, one stock24 no-input, one stock24 input rejected with default off.
- No-input/default-off controls observed virtual 1 ms using the existing timer. Edge/IRQ/callback were 0, gate/timestamp preserved, fault/guard 0. Final SRAM, R0–R15, and time were exact between controls.
- Device suite with new input passed 42 checks. Existing BLE 26 and touch 42 checks also passed separately. Counts include overlapping existing contracts, not independent features.
- Red failed at actual Renode platform load because the runtimePin38 constructor was absent. It was preserved before implementation; other failures were not overwritten as success.
- Saved audit passed 67 judgments. All nine actually owned containers (five original, three unit, one red) were confirmed journal removed and absent in Docker inspect. No new VM ran in the saved audit.

## Next boundary

The initial gate-off GPIO38/IRQ57 path is connected. Predicate/tick/queue → sensor task → IOM4 FIFO → sample consumption after normal initialization remains unverified in natural main. Reuse earlier original FIFO/numeric analysis, but do not force the gate open while normal GAF computation is unsupported. IRQ entry alone does not complete E12.

Evidence is outside Git in `simulator/imu-gpio38-runtime-research-01/` (runner, device checks, baseline/final source, audit), `imu-gpio38-native-01/{stock24,stock23,cfw}`, and two control folders. Full hash list is `simulator/imu-gpio38-runtime-manifest.json`. No physical access, subagents, or external publication.
