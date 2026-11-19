# Development Simulator Based on Stock Firmware

> 2026-11-13 bw342: active scope is emulator-only scope v3. For current status and reproduction, prioritize the [capability catalog](../architecture/emulator-capability-catalog.md); for next steps use the [emulator roadmap](../architecture/emulator-roadmap.md). The text below records an earlier stage; its historical progress, priorities, and initial CPU table are not current status.

Status: the user approved development in this order: execute actual binaries and trace unimplemented accesses → add needed models → connect actual display output, saying “Yes, I approve development in that order.” Start with the first runner scope below. Detailed peripheral models and full-board accuracy were not yet verified.

The user later expanded the active objective itself to a “development hardware simulator based on stock firmware to make firmware development easier” and, if possible, display the screen in the simulator. Screen display is an explicit conditional deliverable. An arbitrarily host-rendered screen does not satisfy this requirement before the actual firmware display path is established.

## Added goal

The user proposed hardware simulation based on stock firmware for CFW development and requested that it be reflected in the goal. Alongside existing goals of web-installable Faceclaw-based CFW and recovery bootloader readiness, build a development/regression environment. Do not reinstate a separate iPhone app as an initial requirement.

The desired final development flow applies the same input scenarios to stock and CFW images and compares memory changes, communications, display results, and error handling. Not every difference is an error. Distinguish intended CFW feature differences from boot/recovery behavior that must be preserved, per scenario.

## Three practical approaches

| Approach | Advantages | Limits |
| --- | --- | --- |
| Execute actual binaries and incrementally add needed peripheral models | Reuse existing Unicorn verification; compare actual patch code | Interrupts, timing, and peripheral models need separate verification |
| Build a full-board emulator | Eventually permits integrated reset-to-communications/display testing | Obtaining Apollo510B, connected chip, ROM, and security-state models is a major prerequisite |
| Software model of HUD and protocol only | Enables quick iteration on screen and web flasher | Not evidence of actual firmware CPU-code behavior |

Recommendation: center on the first, connect the third, and expand to full-board scope as need and evidence accumulate. A screen mock alone is not reported as completion of the requested hardware simulator.

[Unicorn's official introduction](https://www.unicorn-engine.org/) provides a CPU emulation and instrumentation framework. Execution of some functions under the ARM M-class configuration currently used is not evidence that the complete Apollo510B CPU, GPU, memory system, and peripherals were accurately reproduced. Suitability of other engines such as Renode for G2/Apollo510B was not yet verified.

## Phased design proposal

1. Consolidate existing per-version image checks and per-function emulation into common execution and recording. Report input hashes, CPU configuration, initial state, model/stub list, and stop reason.
2. Trace stock and CFW reset/initialization paths under bounded execution budgets. Record address and execution context of unimplemented ROM/MMIO access and stop. Do not return 0 or success for unknown registers in bulk.
3. Deterministically model only peripherals supported by evidence. Consider virtual MRAM/NOR, timers, UART, and BLE delivery boundaries in that order. Power interruption is a failure condition of virtual storage models, not proof of physical power-failure safety.
4. Connect a 576×288 screen viewer and input/sensor scenarios at confirmed display-delivery boundaries. Always distinguish actual renderer output from host-model output. GPU use requires separate investigation.
5. Connect virtual glasses at the web installer's transport boundary and repeat single-temple installation, interruption, and recovery. Do not generalize this to reproduction of browser BLE itself or actual OTA storage behavior.

## Verification contract

- Keep firmware, keys, and private dumps outside Git; pin versions and hashes.
- Do not automatically treat stock baseline results as truth. Distinguish differences caused by unsupported CPU instructions, inaccurate models, and missing ROM state.
- Runs reaching unimplemented boundaries are `unsupported` or `incomplete`, not successful.
- Preserve timer, sensor, and communication inputs as reproducible scenarios. Do not report emulator processing speed as actual FPS, latency, or power measurement.
- Label actual binary execution, source-supported models, assumption-based stubs, and physical observations separately.
- Simulator success alone does not lift the installation gate. Approval boundaries for physical reads, RAM execution, and permanent writes remain.

## What existed and what did not

At this stage there were individual emulations of memory initialization, portions of UART/power callbacks, MRAM wrappers, and boot handoff, plus web communication mock tests. [Handoff verification](../bootloader/combined-handoff-verification.md) stops before executing main reset instructions. An integrated board simulator, full main boot, and display/sensor/radio models did not yet exist.

The recommended first scope is a common runner and detection of unimplemented boundaries in the reset path. Completion of that stage means reproducibly recording stock/CFW stop points and evidence, not completion of the full simulator objective.

## Concrete proposal for first implementation

- Interface: select pinned-hash stock 2.3/2.4 and Faceclaw main from a local CLI. Do not include physical connection capability.
- Execution modes: distinguish isolated execution from main reset entry from continued execution after existing boot handoff. Do not interpret failure of the former as physical cold-boot failure.
- State: code is read/execute-only; virtual RAM initial values and starting registers are explicit. Record that the Unicorn CPU configuration used in existing verification is a limited approximation.
- Stop conditions: first unmapped memory/ROM/MMIO access, unsupported instruction, or explicit instruction/time limit. Preserve cause PC, access address, size, read/write/fetch, and recent execution addresses.
- Repeatability: compare results for identical inputs/initial state. Timeout is not success; distinguish nondeterministic timeout from fixed instruction-budget results.
- Display path: initially provide only trace/memory diagnostics. Once actual display buffer/transfer is established, attach a 576×288 viewer and record frame provenance and representation conversion. Do not claim a glasses screen was generated before a display model exists.
- Verification: use synthetic code to confirm memory-access stops and code-write rejection, and reproduce stop points twice using actual pinned images. Report actual image checks and synthetic unit tests separately.

This first implementation does not promise full-board simulator or display completion. Remaining peripheral models and display path of the larger goal remain.
