# Original Bootloader to Main and Screen Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans inline. User authorizes this goal; no subagents/Astra, physical writes or publication. Existing shared worktree is retained because its project files are uncommitted; no branch copy/commit/push is required for these reversible changes.

**Goal:** Continuously execute and verify the original bootloader reset through original main and a completed screen on the same virtual board.

**Architecture:** The first profile uses stock 2.4 boot/main. Reuse the existing Renode M55, functional devices, and UI/rendering foundation, loading boot into a separate readonly code region. Do not force runtime PC/return/TCB or test results; stop with evidence when ROM or device behavior is unknown.

**Tech Stack:** Pinned Renode 1.17 M55 Docker image e840c2b9…, Python, existing C# models, Capstone, and existing LLVM guest fixtures. Reference proprietary images only through private asset paths.

## Scope and acceptance criteria

The dashboard/JSON are authoritative for the eight original-boot-screen-v1 criteria. Full continuous execution, completed frame, repetition, and negative verification are all required for the first profile. The starting points are bootloader vector 0x410000 (SP2007fb00/reset432cb3), main vector 438000 (SP2007fb00/reset5fbe3f). Do not hide the current absence of Boot ROM bytes with a success stub. Preserve existing 2.3/Faceclaw tests without carrying them forward as automatic compatibility with the new boot path.

## Task 1: Inputs and current execution boundary

Files: docs/original-boot-screen-{plan,dashboard,progress}.md/json; private simulator/original-boot-screen-baseline-bw522-01.

- [x] Read current boot 2.3/2.4 and stock24 main and verify SHA/vectors/length/load addresses.
- [x] Record that the previous combined handoff starts from a patched image and specified PC/R0 and ends before main.
- [x] Add 0x410000 boot mapping to the pinned functional board and measure the first reset's strict execution boundary with the existing memory policy. Do not disable protection or move start PC to main.
- [x] Preserve mutable documents from the previous completed Goal as immutable copies with original SHAs, then update the new goal entry document.

## Task 2: Original boot readonly region

Files: tools/renode-memory-policy.cs; tools/verify_renode_memory_policy.py; tests/fixtures generated only in private output.

- [x] Preserve existing main/ITCM policy and permit `BindBootImage(MappedMemory boot, ulong length)` only before Attach. Distinguish BootBase410000, actual length, and mapping end 438000. Reject boot writes, padding reads/execution, and truncated Thumb32.
- [x] Check normal boot execution, write rejection, padding boundaries, and existing main/ITCM protection using actual M55 guest fixtures. Record failure before the change, then apply the minimal policy change.
- [x] Run `python3 -B tools/verify_renode_memory_policy.py <new-private-path> --case main-write-dword --case guest-written-itcm` for default regressions and boot-specific additional cases with the same tool. Retain new output, frozen source, manifest and image ID; clean ELF/intermediate builds after verification while preserving reproduction commands and analysis.

## Task 3: Continuous-execution runner

Files: tools/run_original_boot_screen.py; tests/test_original_boot_screen.py; pinned board/assets reused from tools/run_renode_m55_probe.py, native_process_recovery.py, and run_sustained_screen.py.

- [x] `derive(profile, output)` pins original boot/main SHA, raw flash ranges, initial SRAM/ITCM fill, board/model sources, observation source, and budget in a manifest. The entrypoint sets only bootVectorTableOffset and rejects forced PC/registers during execution or unchecked ROM function returns.
- [x] `run(output)` executes sequentially using existing owned-container creation/cleanup. `audit(output, audit_output)` verifies actual trace/state/frame against original and pinned source and distinguishes execution_passed from semantic_passed.
- [x] Record the first unsupported boundary's address/width/value/PC, before/after state, original function, and version evidence. Reuse verified device behavior and add only evidence-backed contracts matching actual boot requests. Leave insufficient ROM/status information unknown.

## Task 4: Original selection, handoff, main, and screen

- [x] Trace original boot selection/check paths and metadata references from actual instructions/bytes. Distinguish transport headers from flash state and load only what the original uses from legitimate assets.
- [x] Observe VTOR/MSP/PC and SRAM/device state provenance at original handoff to confirm natural arrival at main reset. Do not replace SRAM with a main snapshot or swap devices into a new machine.
- [x] Obtain a 576×288 detailed frame from subsequent main/RTOS/UI/original GPU commands/packing; preserve raw SHA and directly inspected preview. Do not claim execution began from ROM.

## Task 5: Reproduction, rejection, audit, and cleanup

- [x] Verify identical boot/main/board/observation configuration and handoff/main/UI/frame in two runs with the same cold inputs.
- [x] Execute negative inputs to ensure corrupt images and unsupported ROM/device boundaries are not reported as success. Distinguish original error branches/CPU faults from observation failure.
- [x] Independently audit one-command execution and --audit-existing reverification, pinned source/input manifest, and evidence for the current eight conditions.
- [x] At each task's end clean reproducible intermediate builds/caches/one-off containers. Preserve key analysis/originals/input hashes/reproduction commands/final evidence. Record duplication and results using start/progress/finish for each task.

If a major unsupported boundary is found, refine the plan into verifiable units analyzing the exact required effect. Do not reduce conditions or denominator to declare completion, or expand authorization to physical access, Astra, or external publication.

Follow-up bw539–543: Verified OB05 actual VTOR/active SP/MSP/PSP provenance and arrival at main reset. Handoff loads PSP under CONTROL2 and does not force MSP to match vector SP. Rewrites of the same VRCTRL value, VDDF low 7, ADC power, and timer period needed for main warm initialization were verified against original/SDK/DFP. The 10-second run had guard/fault 0, frame 0. Same-model 20-second observation bw544 was next; overall 5/8 unchanged.

bw548: tools/run_original_boot_screen.py and pinned profile passed 14 verification conditions, normal CLI and separate 30-condition audit. The model is verified private frozen source; firmware is not distributed. Runner documentation is docs/bootloader/original-boot-reproduction.md. The first CLI's host preview quadratic-cost interruption 130 was preserved; after verifying postprocessing recovery without native restart, a new run of the corrected CLI was completed. Repetition/negative/final audit remained incomplete.

Final bw550: Completed actual evidence audit of original eight conditions and plan artifacts/commands/protection/cleanup. Preserved two final normal cold cases, original unsupported boundary, host corruption rejection, 14 tests, and separate audit. See docs/bootloader/original-boot-completion-audit.md and private original-boot-final-audit-bw550-01/report.json. All plan checks complete; the later unapproved precision Goal is not activated.
