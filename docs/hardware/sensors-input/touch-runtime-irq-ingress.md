# GPIO27 IRQ56 and original input-task resumption

bw442. **Actual original three main resets → normal hold → GPIO27 falling edge → IRQ56 → registered callback → input queue/task flag → original `input` task → IOM5 frame consumption → original caller return** was connected. This advances from [bw441](touch-event-bus-ingress.md)'s initial-low sample to actual runtime IRQ delivery.

Overall 10/16=62.5% and API 3/6 remain. E11 gesture/ring support list and app/UI consumption are incomplete; one touch does not reduce scope or complete it.

## Original configuration and callback contract

Actual vector tables, dispatchers, and saved SRAM pointer tables of each supported image were compared. Existing pinned main hold was used without regenerating source material with the current builder.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| pin / bank / IRQ | 27 / 0 / 56 | Same |
| ISR | `0x4fc8e8` | `0x557510` |
| Registered callback | `0x4fc328` | `0x579bc8` |
| Queue producer | `0x5052ae` | `0x52f252` |
| Task flag | `0x400000` | Same |
| Queue depth / item size | 30 / 12 bytes | Same |

ISR reads IRQ number 56 from flash context and calls status → clear → dispatcher; it was not assumed to be a direct immediate constant. Registered callback constructs message 0, enqueues it, and signals a task flag. Original handle's TCB name is `input`, and queue waiting messages are 0.

Original PINCFG27=`0x53` and bank0 enable bit27 were confirmed. They correspond to eIntDir bits 7:6 and HI2LO=1 in the existing pinned Ambiq GPIO header, meaning falling edge in original configuration. Physical idle voltage/polarity and touch MCU physical clear delay were not confirmed. Do not confuse this with BLE pin117 rising edge/IRQ59.

## Shared GPIO model extension

Default-off `runtimePin27` selection was added to `BlackwallGpioInterruptIdle`. This virtual profile's initial line is high; with configured=true, high→low latches pending27. Bank0 mask determines IRQ56 output and original clear write clears pending. Held-low or rising transition creates no new falling edge.

IRQ27 and existing IRQ59 output/pending/clear are separate. Units confirmed simultaneous retention and independent clear. Two GPIO outputs caused regression due to ambiguous existing unnamed wiring; `[DefaultInterrupt]` on the existing IRQ restored compatibility. This was confirmed with [Renode's official example](https://github.com/renode/renode-infrastructure/blob/master/src/Emulator/Peripherals/Peripherals/Timers/STM32_Timer.cs), actual compilation on pinned 1.17 image, and legacy units. Existing boards were not bulk modified.

Profile Reset reinitializes pending/counters/virtual initial line. CPU/controller reset versus external touch-source level/intermediate-read lifetime is a separate E06 audit, not a physical reset claim.

## Actual M55 results

Input is bw441's `02400aa73412cdab0180ffff5ac317e9`. After original hold in existing runner, observation alone was attached and a device GPIO edge supplied. CPU PC/general registers/TCB/stack/branches/returns were not specified, and bus/RTOS leaves were not replaced by ABIs.

| Judgment | Stock 2.4 | Stock 2.3 | Faceclaw38 |
| --- | --- | --- | --- |
| Pre-injection CPU report / full SRAM | Exact against baseline | Exact | Exact |
| Registers / full SRAM before and after injection | Exact | Exact | Exact |
| Actual ISR / callback | IRQ56 / registered callback once each | Same | Same |
| ISR/callback IPSR | 72 (56+16) | Same | Same |
| Consumer task / IPSR | `input` / 0 | Same | Same |
| IOM5 read / frame | four chunks / 16 bytes exact | Same | Same |
| Wear notification / slider arguments | `[3,2]` / `[1,4,10,167]` | Same | Same |
| Original caller return | `0x5053b4` | `0x52f358` | `0x52f358` |
| Function entry/return SP / TCB | Same / same | Same | Same |
| pending / IRQ56 | Cleared by original clear | Same | Same |
| queue / CFSR / HFSR / memory violations | All 0 | All 0 | All 0 |

During IRQ, TCB belonged to the interrupted sensor task; original RTOS subsequently selected a different `input` TCB and original stack. Caller return addresses came from comparison of previous actual handler LR and corresponding original BL, not by applying stock24 prototype addresses to other versions.

Unlike earlier observation of function epilogue alone, return to actual caller instruction with same SP/TCB was confirmed and whole machine paused. Subsequent GPIO level reread/physical read-clear relationship and final app/screen consumption were not followed. Original clearing pending is distinct from touch-source line physically returning high.

## Error/no-input controls and preserved failures

Stock 2.4 error input changing only first byte to 3 also passed actual IRQ56/callback/input task. The 16-byte read completed, but no proximity notification or slider dispatch occurred; state 0/queue 0 remained and it returned to the same caller.

First no-input control used synchronous `RunFor(500us)`. The call did not finish after VM abort and was terminated at a 150-second host limit; owned container was cleaned up. It is not counted as success or firmware timeout. An asynchronous diagnostic of the same no-input collected original IOM4 CMD boundary `PC0x58236c / address0x40054120` and IRQ/handler 0. This corresponds to an existing legacy IMU model GAF getter gap, not a new touch-input failure or physical fault.

The final no-input control used the existing [verified GAF parameter profile](../../architecture/runtime-gaf-profile-integration.md) and existing timer helper to stop the whole machine after exactly 1 virtual ms. No normal-computation ready was added. IRQ/handler/frame/chunk/edge were all 0, queue 0, CFSR/HFSR and protection violations 0. It is not a control with the same background GAF component as input runs; that difference is explicit. It is not evidence of normal GAF computation or full initialization success.

## Verification and preservation

- Five passing original M55 scenarios: three normal, one error, one no-input. One failed no-input RunFor and one frontier diagnostic are also preserved, seven actual ARM attempts.
- Final 42 GPIO device checks cover default off, configuration rejection, falling/mask/pending/clear, held level, IRQ56 wiring, BLE simultaneous/independent clear, and reset. Existing BLE 26 checks passed too.
- Initial red lacked runtimePin27 constructor. Default IRQ ambiguity failure and native builder duplicate metadata-key preflight failure were also preserved. Builder preflight did not start a VM.
- Inputs, logs, full SRAM, and model are preserved in private `touch-runtime-irq-research-01/source-contract.json`, `verification-report.json`, builder/verifier/original disassembly, `touch-runtime-irq-native-02`, and error/no-input/unit folders.
- `touch-runtime-irq-manifest.json` pins original source, actual outputs, and final code/doc snapshot by size/SHA. The VM stuck in synchronous RunFor was not resumed and all owned journals are removed.

No physical access, flash, subagents, or external publication. No universal observation-hook noninterference or actual physical delay is claimed. Pre-injection exactness checks cold-path preservation, not neutrality of all runtime observation.

## Next work

Follow-up [bw443](touch-app-consumer-contract.md) connected GPIO27 subsequent reads and original UART transmission. App callback remained unobserved there; the next boundary was valid peer reply and local delivery. Below is the plan at bw442 completion.

Next connect **registered app consumers and state/UI changes** rather than ending at input dispatch. Handle GPIO27 post-read level/reread and additional-input lifetime with declared source contracts, not automatic high. Check unresolved gesture/ring list against original support and goal criteria. Recheck no-input/error/duplicate and supported-input scope in full E11 completion audit without narrowing scope to raise progress.
