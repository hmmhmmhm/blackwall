# Current simulator fidelity

> 2026-11-13 bw342: The active scope is emulator-only scope v3. For current status and reproduction, prioritize the [capability catalog](emulator-capability-catalog.md); for the next steps, use the [emulator roadmap](emulator-roadmap.md). The following records earlier stages; do not treat historical progress, priorities, or the initial CPU table as current status.

At this stage it is a **partial system emulator** that executes actual ARM firmware instructions and selectively models necessary peripherals. Full chipset and G2 board reproduction and complete boot remain incomplete.

| Layer | Implementation at this stage | Verification limits |
| --- | --- | --- |
| Function and protocol tests | Execute individual firmware functions and test OTA transport with a virtual peer | Does not guarantee reachability in full firmware or communication with physical devices |
| Main runner | Execute actual instructions from reset vector of pinned stock and Faceclaw mains | Different from a full board boot starting at the bootloader |
| CPU | Unicorn Cortex-M4 model | Does not reproduce the full Cortex-M55 instructions, exceptions, security, or timing of Apollo510B |
| Renode CPU reuse test | Execute some MVE, SVC, PendSV, IRQ0, and SysTick on M55 in Linux ARM64 | Isolated core test; Apollo510B peripherals are not verified |
| Initial Renode main integration | Run two stock images and Faceclaw from reset to the first power register read | Aborts at unimplemented MMIO; subsequent peripherals and full boot are incomplete |
| Initial Renode fixture | Run to first watchdog access with LP/HP and reset shadow assumptions | Does not reproduce actual power and reset behavior |
| Renode watchdog | Run LFRC-assumed count, IRQ and reset-request boundaries and initial main CFG setup | Standalone setup does not evaluate gate; system reset and full boot unimplemented |
| Renode reset controller | Decide CFG two bits and watchdog gate; main advances to DEVPWREN access | System reset, retention, and next boot unimplemented |
| Renode initial control extension | Reach SHADOWVALID under peripheral/debug OFF, core ON, and WIC storage assumptions | Actual power transitions, wakeup, and Info1 calibration data unimplemented |
| Renode Info1 conditions | Reach CHIPREV with source bit and three invalid metadata words; OTP path stops at power request | Actual calibration values, OTP contents, and chip revision are not supplied |
| Renode silicon conditions | Four virtual revision branches and limited ACRG/VRCTRL storage; reach memory power state/additional Info1 | Actual revision detection, voltage, and power stabilization unimplemented |
| Renode memory policy | Block main writes, out-of-range reads/execution, unwritten ITCM instructions, and SRAM execution | For single-main tests; not verification of DMA, full reset, or physical memory protection |
| Renode memory power conditions | Reach CLKGEN using ON assumption, single ROM OFF, and retention/override storage | Actual power, sleep, retention, and transition delay unimplemented |
| Renode initial HAL storage | Connect 24 clock, ADC, public reset, switch, TON, and HALSTATES addresses to reach MRAMEXTCTRL | Actual clocks, analog behavior, valid calibration, and MRAM wake-up unimplemented |
| MRAM control storage | Connect public reset 2 and 2→6 storage to both engines and reach the next VRCTRL write | Actual MRAM wake-up, delay, power, recall, and contents unimplemented |
| VRCTRL override sequence | Store observed SIMOBUCK and core/memory LDO 10-step sequence, then reach SIMOBUCK15 | Actual voltage, switching, DeepSleep, and subsequent buck activation unimplemented |
| SIMOBUCK start request | Store trim latch, compensation, and enable requests and block readiness; actual main stops at LDOREG1 write two steps later | Actual enable arrival, calibration, power readiness, and analog effects unverified |
| Core LDO reduction storage | Connect step-limited reduction after checking original helper arithmetic; actual main stops at LDOREG2 write after enable request | Valid factory calibration, voltage, power readiness, and subsequent memory LDO unverified |
| Memory LDO configuration storage | Connect order-limited storage after checking original helper for two fields; actual main stops at VRSTATUS read | Analog stabilization, status response, and full boot unverified |
| Buck status branch test | Explicitly provide one of OFF, LP, ACT once; ACT VREFGEN4 write boundary matches in both engines | Actual power response unverified; default OFF/LP paths stop at first cache access, functional model selected separately |
| PFCR control storage | Store defined 10-bit fields after first explicit write; 12 OFF/LP combinations match at D-cache selection write | Actual prefetch, cache geometry, and full boot unverified |
| Functional-test instruction memory | Default cache access rejection and optional coherent instruction memory; 12 OFF/LP combinations match at PFCR write | Physical cache, delay, replacement, DMA coherence, and full boot unverified |
| Functional-test data memory | Document-based 64 KiB geometry, set/way initialization and clean; 12 actual main combinations match at second buck status read | Physical cache, power response, full boot, and integrated display unverified; [details](../hardware/cpu-memory/coherent-data-cache-model.md) |
| Explicit buck response and initial VDDF storage | Virtual ACT/stuck-off response after request and LDO setup, one calibration stored; six main combinations match at clock request write | Instantaneous digital assumption; voltage, periodic calibration, full boot, and integrated screen unverified; [details](../hardware/power/buck-state-response-model.md) |
| Memory and peripherals | Selected SRAM/ITCM, watchdog, and some control registers | Includes virtual initial conditions; unimplemented accesses stop execution |
| Screen | Execute actual upstream drawing code in a separate ARM build to generate framebuffer/PNG | Neither a screen generated by full CFW boot nor actual display transport |

A Python rewrite of stock functions is not reported as main execution. The main runner executes original ARM code, with virtual hardware handling only MMIO accesses. Some isolated function tests stub external calls such as files, communications, and logging, so consult each report's execution scope and stub list.

The development goal is a virtual G2 board on which display, input, and communication behavior can be compared while running actual CFW. Individual function tests or PNG generation alone do not complete that goal. Necessary unimplemented boundaries, including BLE, display transport, sensors, interrupts, and CPU differences, remain to be resolved. Physical voltage, power consumption, transport delay, and recoverability after failure cannot be guaranteed without separate verification.

For the execution boundary see [runner status](simulator-runner-status.md), for reproduction see [usage](simulator-usage.md), and for the isolated screen test scope see [renderer probe](../archive/cfw-renderer-probe.md).
The new CPU reuse path is recorded in the [Renode M55 test](renode-m55-probe.md).
Subsequent actual-image integration is recorded in the [Renode main test](renode-main-probe.md).
Power and reset input assumptions are recorded in the [initial fixture test](renode-startup-fixtures.md).
Time-based peripheral expansion is recorded in the [watchdog test](renode-watchdog-model.md).
Optional reset gate integration is recorded in the [reset-controller test](renode-reset-controller-model.md).
Subsequent initial control conditions are recorded in the [startup controls test](renode-startup-controls.md).
Information-area conditional branches are recorded in the [Info1 test](renode-info1-fixtures.md).
Revision-specific initialization comparisons are recorded in the [silicon conditions test](renode-silicon-fixtures.md).
Default memory protection is recorded in the [memory policy](renode-memory-policy.md).
Memory power condition integration is recorded in the [memory startup test](renode-memory-startup.md).
The subsequent storage range is recorded in the [initial HAL storage test](renode-hal-startup-storage.md).
Subsequent MRAM control is recorded in the [control storage test](../hardware/cpu-memory/mram-auto-wakeup-control.md).
The next initialization is recorded in the [override sequence test](../hardware/power/buck-ldo-override-sequence.md).
The start request and readiness boundary are recorded in the [start request test](../hardware/power/buck-start-request-storage.md).
Limited storage of initial calibration is recorded in the [core LDO reduction test](../hardware/power/coreldo-saturated-reduction.md).

Subsequent PFCR configuration and D-cache information blocking follow the [control storage record](../hardware/cpu-memory/prefetch-control-storage.md).

## HFRC2 and MCU performance transition response verification

The [clock response model](../hardware/power/hfrc2-mcu-mode-response.md) was added. Limited state comparisons were verified with 122 Python and 12 native conditions and six combinations of two stock images/Faceclaw × LP/HP. M55 proceeds past MPU control code and additional cache cleaning to a PWRCTRL.GFXPWRSWSEL (0x40021090) read. Python stops at SHCSR, so this is not interpreted as endpoint equivalence, full boot, or integrated screen success. Assumptions including zero response delay, synthetic initial values, and ready apply only to selected scenarios and are unverified on physical hardware.

## GPU supply source and performance request storage

The [GPU selection storage model](../hardware/display-gpu/gfx-power-selection-storage.md) was connected to native M55. Limited verification passed in 15 synthetic conditions, three existing-behavior regressions, and six main combinations. Original main advances to CLKGEN.MISC.FRCHFRC write (0xfbbfc1) after storing selection 1 and request 3. GPU engine, physical clock/voltage, full boot, and integrated screen remain incomplete. Python retains the earlier MPU boundary.

## HFRC force control

The [HFRC control model](../hardware/power/hfrc-force-control.md) was added as opt-in. Limited verification completed for seven native conditions, four existing-behavior regressions, and six original main combinations. M55 advances past MISC=0xfbbfe1 to the point of attempting to write 0x6d3d9 to LDOREG1 (0x40020080). Actual clock, voltage, full boot, and integrated screen remain incomplete. The difference from the Python MPU boundary is retained.

## 18 GPU power preparation steps

The [power preparation sequence](../hardware/display-gpu/gpu-power-preparation-sequence.md) was connected as an optional native model. In 10 synthetic cases, four existing-behavior regressions, and six main combinations, execution passed calibration/rail/TON/restoration and reached the DEVPWREN GPU bit 18 request (0x40021004,0x40000). Physical power, GPU engine, app loop, and integrated screen remain incomplete.

## GPU power request and status response

The [GPU power response](../hardware/display-gpu/gpu-power-domain-response.md) was connected as an optional model. In 13 synthetic cases, four existing-behavior regressions, and six normal main combinations, execution advanced after power status on to the first GPU.INTERRUPTCTRL (0x400900f8) write. A stock 2.4 stuck-off observation also advanced to the same GPU access, failing to establish safe failure fallback or recovery. GPU engine, full boot, and integrated screen remain incomplete.

## GPU initialization evidence and IRQ28

The [GPU initialization investigation](../hardware/display-gpu/gpu-initialization-research.md) compared static patterns in three pinned firmware images with the official Apollo510 HAL. A separate M55 synthetic test confirmed IRQ28 pending/clear/handler entry. GPU IRQ integration and command execution are unimplemented, and the actual main execution endpoint remains as before. The ARM driver archive inspected does not replace a GPU execution model. Full boot and integrated screen remain incomplete.

## Initial GPU interrupt clear

[GPU idle clear](../hardware/display-gpu/gpu-interrupt-clear-model.md) was connected to the explicit power response. It handles only DWORD0 writes in the virtual on state and does not create GPU work, completion IRQ, or reset. Nine synthetic and four power regression cases were checked. Full boot and integrated screen remain incomplete.

## Initial GPU ID and ring candidate capture

[Initial ID0 and ring observation](../hardware/display-gpu/gpu-id-initialization-capture.md) was added. Thirteen synthetic and four LP main cases were checked; in active 3, while blocking the 0xec request, an initial footer matching 4864 bytes was observed. GPU command execution, full boot, and integrated screen remain incomplete.

## Initial GPU ring configuration

The [configuration latch model](../hardware/display-gpu/gpu-ring-configuration-model.md) was connected. Seventeen new cases, four regressions, and four LP main cases were checked. Active 3 stops at the GPU IDREG 0x400901ec read after three configuration steps, preserving initial ring snapshots of 1216 words each. GPU execution, full boot, and screen remain incomplete.

## Fixed GPU ID response

The public 0x86362000 and literals of the three inputs were compared and compiled offsets checked in the [fixed ID comparison and response](../hardware/display-gpu/gpu-identity-response-model.md). Twelve native and five main cases were observed. Normal 3 advanced to GPU 0xe8 write, absent stopped at fc read, and stuck-off at f8 write. Actual GPU capability, safe fallback, full boot, and integrated screen remain incomplete.

## Initial GPU reset request

[Limited initial reset control](../hardware/display-gpu/gpu-initial-reset-controls.md) was connected. Fifteen native and four LP main cases were checked; normal 3 stopped at 0x388 write after e8/fc requests. Ring validity after reset is unconfirmed, and active GPU reset, GPU command execution, full boot, and integrated screen remain incomplete.

## Initial-value observation mode and pending command candidates

In [optional trace-only recording](../hardware/display-gpu/gpu-raster-init-storage.md), RAST initial value 1 was recorded opaquely, and execution advanced to CONFIG read 1f0. Default remains the earlier 388 block, and rendering effects are unimplemented. The initial 25 candidate pairs and 35 word changes prepared by the CPU in RAM were confirmed. GPU execution, submission length, full boot, and screen are unverified.
