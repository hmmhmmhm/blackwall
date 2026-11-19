# Scheduling Dependency Between GAF Execution and the Natural Renderer

bw-0450. The bw449 UI broadcast completed, but the config-only model later stopped at sensor_hub GAF request 2. This work reused the existing explicit frozen-core fault model to check state after that request. A fault scenario does not replace normal GAF calculation, service initialization, or display success. Overall progress remains 10/16=62.5%.

## Preserved inputs and model boundary

The new candidate uses `probe_gaf_frozen_core.compose_frozen`. This verified fault profile supplies requests 2/4 and persistent busy to the existing GAF on-demand control contract, without producing calculation results. It does not bypass the 225-byte configuration input, clock trim fixture, or existing service completion conditions.

Original main, device models outside the IMU namespace, and existing UART/GPIO/clock/RTOS protection remain unchanged. New board inputs select GAF on-demand control and 1000 µs; the frozen-core profile does not transition to ready at that time. The existing HAL-derived HP interval remains. Four SRAM snapshots—initial, UI dispatch, app1 callback return, and broadcast return—are byte-identical to the config-only candidate. The model difference did not alter original initial state before the GAF request.

After UI broadcast, execution is limited to 20 virtual ms and 30 host seconds. Firmware's 200,000 GAF waits, watchdog, task priority, PC, TCB, and returns are unchanged.

## Actual original execution

Original GAF request 2 was accepted and completed the original A272 clear → 2A enable → 73 trigger transaction. The result was requests 1, triggers 1, busy 178, pending=true, calculation supported=false, completed calculations 0. History was `request:2|a272:1f|2a:cb|73:e9`; there were no model rejections.

After preserving original UI broadcast return, execution advanced about 20.023 ms. Final PC `0x5821d4` is inside original IOM HAL. Strict accesses, CFSR/HFSR, memory protection violations, and observation overflow were 0. Draw, target, submit, ring, display producer, and frame wrapper remained at 0 calls. The host did not return the original wait or inject ready.

## Renderer is already ready

Ready-list addresses in the connected original task graph were independently derived from the selector's literal. In both snapshots (config-only request 2 boundary / after frozen-core busy):

| Task | Priority | State | Notification count |
| --- | ---: | --- | ---: |
| sensor_hub | 41 | Actual current, in ready-list[41] | 0 |
| ambiqdraw | 40 | In ready-list[40] | 1 |

Scheduler running is 1, suspended 0. Thus the explanation that no notification reached the renderer does not match the saved state. Ready-list membership, node dereference, current task, and saved stack context were checked; unlinked candidates were not counted as actual tasks.

Using the same two SRAM snapshots, the **original ARM scheduler selection function** was executed in an isolated Cortex-M7 fixture. Both cases returned normally and selected sensor_hub/priority 41 again. No hooks or original opcode replacements were used. Only permitted fields written by the function, such as selector history and list cursor, changed. This isolated check did not reverify native M55 PendSV/exception return execution itself, and modified task state was not written to the native machine.

Original GAF wait `0x555976` queries A297 bit 1 and repeatedly calls a 5 µs delay helper while incomplete. Its direct calls are the original read helper and delay wrapper. This and selector results for the snapshots support a dependency involving the higher-priority sensor task's busy wait. They do not prove scheduling at all times, permanent starvation, or behavior of a normal device.

## Next work and completion boundary

This profile can pass the strict stop on the unsupported request itself, but that alone did not run the natural renderer. Focus shifts to normal GAF execution/return contract and the sensor initialization path, rather than additional ready notifications or simply waiting longer. Do not repeat the frozen-core timeout → request 4 → WDT history as evidence of normal calculation.

The lack of normal GAF ROM/ISA and input/output oracle follows the [existing execution contract investigation](gaf-edmp-execution-contract.md). Do not bypass opcodes, priority, or required initialization to mark the integrated display complete. E05/E09/E12 and pixels/continuous frames remain incomplete.

Twenty-three saved audits and exact results from two separate original selector reruns were confirmed. Audit scope covers original/model boundary, state preservation, actual fault control/no calculation, ready-list and notification, original selector results, and protection/process cleanup. Snapshot inference is distinguished from separate ARM execution.

Material is preserved with hashes in private `simulator/gaf-render-scheduler-research-01`, `gaf-render-scheduler-native-01`, and `gaf-render-scheduler-manifest.json`. No physical access, permanent writes, subagents, or external publication occurred.
