# Original Bootloader→Main→Screen Dashboard

**Complete: 8/8 (100.0%) — original-boot-screen-v1.** This denominator differs from the previous 6/60-second Goal 10/10 and v3 functional scope 16/16.

The first supported combination is stock boot2.4.0.24→main2.4.0.24. Execution starts at the original boot reset vector and must continue through UI/frame while preserving the same board/memory/peripheral state after main entry. Full Boot ROM reset is not the starting point of this scope. Applicability to existing 2.3/Faceclaw is reported separately; unverified combinations are not counted as passing.

| Condition | Completion criterion | Status |
| --- | --- | --- |
| OB01 | Pin original bootloader/main provenance, SHA, vectors, and load addresses | Done |
| OB02 | Execute actual initialization code on M55 from the original boot reset vector without branch bypass | Done |
| OB03 | Configure required boot code-region protection and peripheral/ROM contracts using evidence; block unknowns | Done |
| OB04 | Verify original image selection/checks, required metadata, and path to handoff | Done |
| OB05 | Execute original handoff→main reset continuously on the same virtual board and confirm VTOR/MSP/PC and state provenance | Done |
| OB06 | Connect RTOS/UI→original render→completed 576×288 frame from that main and inspect it directly | Done |
| OB07 | Verify two identical cold inputs and rejection of corrupt inputs/unsupported boundaries | Done |
| OB08 | Complete reproduction command, pinned manifest, comparison/final audit, and per-task artifact cleanup | Done |

OB01 read both actual boot images and stock24 main and verified SHA/SP/reset vector/addresses. The previous patched handoff test began with specified hook/R0 and ended before the first main instruction, so it is not reused as continuous boot evidence.

Configuration gap found in initial diagnosis, subsequently resolved: main's BlackwallMemoryPolicy permits execution only in 0x438000 main and guest-written ITCM, so the 0x410000 original boot region must be explicitly added with protection. Do not arbitrarily disable the code-execution guard.

[Implementation plan](original-boot-screen-plan.md) · [Machine record](../data/original-boot-screen-progress.json) · [Previous completed Goal](../hardware/display-gpu/sustained-screen-dashboard.md).

The first native diagnosis was blocked as expected at SP2007fb00/PC432cb2 with execute-outside-code 1/instructions 0/MMIO 0. This was not successful original bootloader execution and OB02 was incomplete; adding source/image protection scope was next. Private `original-boot-screen-baseline-bw522-01/baseline-proof.json`. One-off Docker removed; readonly original references avoided duplicate image copies; -B produced no cache.

Subsequent original execution: reset→CRT/FPU→C initialization→data initialization→bootloader internal C main each executed once in order. All original boot bytes matched after execution; 1024153 instructions/virtual 102.4153ms, actual 24-byte ITCM write, code/system/unsupported access errors 0. Target application main reset/handoff/frame were not yet reached; this was not full boot success. Confirmed original countdown delay at ITCM40 and boot C main first argument 200→×1000. [Initial execution analysis](original-boot-startup-frontier.md).

Latest bw524: original delay 6399985→0 returned naturally→init dispatcher/board init reached. Strict stop on shared power 40021004=2000 write at PC41c05c; investigate previous value/XOR/owner. Model/original unchanged, main app/frame unreached, 2/8 retained.

Latest bw525: before 0→proposed 2000/XOR2000 and other owners preserved established ADC bit13 request. Model buck phase off did not meet ADC allowance active condition. Next verify boot initial power/calibration contract without forcing runtime phase/state. Guest registers/instruction count/boot globals exact before/after observation. Progress 2/8 retained.

bw526: Confirmed original boot ADC automatic calibration disabled/buck off request and removed only excessive buck conditions at two ADC dispatch points. Cold 44 items/existing 20 conditions passed. After 13,789,871 original instructions and one ADC request/response, reached PC426fc4, 40004044=1 write boundary. Main/frame unreached, 2/8 unchanged. [ADC contract](original-boot-adc-cold-contract.md). Cleaned 20 ELF files totaling 676864 bytes and two identical boot dumps totaling 299546 bytes; owned Docker removed.

bw527: Separated buck conditions for HFRC/2 control and MCU mode; cold 12 items/existing 10 conditions passed. After 13,791,447 original instructions, reached 40021004=400 power-request boundary. Main/frame unreached, 2/8 unchanged. [Clock contract](original-boot-cold-clock-contract.md). Cleaned ELF/identical dumps 485465 bytes; owned Docker removed.

bw528: UART cold 35/HCPA38/ADC40 items passed. After one original UART1 power request/response and CR8 configuration, reached 400201b0=0 write boundary. Main unreached, 2/8 unchanged. [UART contract](original-boot-cold-uart-contract.md). Cleaned identical boot 149773 bytes; six owned Docker containers removed.

bw529: Cold UART clock 26/adapter 117 items passed. After 13,796,407 original instructions, reached 40021004=8 power-request boundary. Main/frame unreached, 2/8 unchanged. [Clock selection contract](original-boot-uart-clock-contract.md). Cleaned identical boot 149773 bytes; seven owned Docker containers removed.

bw530: IOM cold 30/extended lifecycle 45 items passed. After 14,018,873 original instructions, reached PC41c5c8, 40004044=fbbfc1 write boundary. This changes fields other than existing HFRC bit0, so do not expand the mask before source comparison. Main/frame unreached, 2/8 unchanged. [IOM contract](original-boot-cold-iom-contract.md). Cleaned identical boot 149773 bytes; four owned Docker containers removed.

bw531: Original/SDK gate 16-field OR=fbbfc0 and force preservation synthetic verification 26 items/existing clock 10 conditions passed. After 14,019,530 original instructions, reached PC426fd8/HFADJ40004020 read boundary. Main unreached, 2/8. [Gate contract](original-boot-clock-gate-contract.md). Cleaned ELF/identical dumps 485465 bytes; owned Docker removed.

bw532: DFP HFADJ reset25b800/disable storage 14 items passed. Budget expired after 20,092,252 original instructions/virtual 2.009 seconds, guard/fault 0 (PC40 original delay, entry 2027/return 2026). Main unreached, 2/8. [HFADJ contract](original-boot-hfadj-disable-contract.md). Cleaned identical boot 149773 bytes; three owned Docker containers removed. Next increase budget without changing model.

bw533: Model/board unchanged, budget increased to 10 seconds. At 39,954,475 original instructions/virtual 3.9955 seconds, reached PC41c222, request 8400→400/XOR8000 MSPI1 off boundary. Delay entered/returned 9247 times, code/system faults 0. Main unreached, 2/8. [Extended observation](original-boot-extended-observation.md). Cleaned identical boot 149773 bytes; owned Docker removed.

bw534: Confirmed PIO idle/FIFO0/CQ and DMA disabled at MSPI1 stop, exact before/after observation. Restored existing main pre-start retention callback omission (model/protection changes 0); existing 39 items passed. After 41,312,219 original instructions/virtual 4.131 seconds, controller off 36/PIO 1317 completed, guard/fault 0, host 120-second budget expired. Main unreached, 2/8. [Connection setup](original-boot-mspi1-retention-setup.md). Cleaned dump/seed 299556 bytes; three owned Docker containers removed.

bw535: Same model, 4.2 seconds/42,000,289 instructions, guard/fault 0. Actual UART1 1110 bytes confirmed NOR scan success, C22539 recognition, and /firmware creation. Stack 42144f was compared with original directory-log caller. Repeated power transitions were not treated as initialization retry failures. Main unreached, 2/8. [Diagnostics](original-boot-retry-diagnostics.md). Cleaned identical boot 149773 bytes; owned Docker removed.

bw536: Control removing two delay observation points yielded UART 1110 bytes/NOR/boot globals exact. At subsequent 51,785,412 original instructions/5.1786 seconds, reached boot manager once, DFU task start/end, and LittleFS boot_count1. Next was PC42e582/7fe000 MRAM metadata read guard. Main/frame unreached, 2/8. [Observation control/progress](original-boot-focused-observation.md). Cleaned dump 299546 bytes; owned Docker removed.

bw537: Existing cleared-marker original boot read 20 items passed. After one read of 7fe000=ffffffff, original selected no-update/GO TO APP and recorded SP2007fb00/reset5fbe3f. Next PC41ba1a/MCUPERFREQ15 LP write guard. Handoff/main unreached, 2/8. [Metadata contract](original-boot-selection-metadata.md). Cleaned dump 149773 bytes; three owned Docker containers removed.

bw538: LP 17/regression 11 conditions passed; original boot manager→handoff→main reset each reached once continuously. Handoff/main r0 438000, final VTOR438000, code/system faults 0. New main PC495c96/VRCTRLfe1ef write guard. Normal boot profile OB03/04 complete, 4/8=50%; simultaneous MSP observation/screen/repetition/final audit incomplete. [LP/handoff evidence](original-boot-pre-handoff-lp.md). Cleaned ELF/dump 888253 bytes; owned Docker removed.

bw539: Guest MRS/MSR controls 18 items, original CPU context at three points confirmed. Main entry VTOR438000/active SP=PSP2007fb00/MSP2007fa90/CONTROL2 matches original LDR SP. Previous execution CPU/SRAM exact; guest boot/main bytes exact. OB05 complete 5/8=62.5%. Established main rewrite boundary VRCTRL before=proposed fe1ef/XOR0. [Provenance](original-boot-handoff-context.md). Cleaned dump/ELF 3950005 bytes; five owned Docker containers removed.

bw540: Allowed only rewriting the same completed VRCTRL value; isolated 19/ARM 20 conditions verified. After 71,980,482 original instructions/virtual 7.1981 seconds, reached VDDF trim4002004c=1fefac boundary at PC5c1b40. Main/frame incomplete, 5/8 unchanged. [Warm VRCTRL](original-boot-warm-vrctrl.md). Cleaned duplicate image/ELF total 4,518,041 bytes; owned Docker removed.

bw541: Established boot trim 64→54/main cache 54→44; observed CPU/events/globals exact. Applied low7 RW contract, ARM 11 conditions passed. After 72,069,245 original instructions/7.207 seconds, reached ADC powered-off re-enable boundary 40021004=2000. Screen 0, 5/8 unchanged. [VDDF contract](original-boot-warm-vddf.md). Cleaned two native duplicate dumps and ELF totaling 8,102,658 bytes.

bw542–543: Verified ADC request after completed power-off and stopped timer restart. Scan/power/timer 109 conditions passed. After one ADC cycle each in original boot/main, budget expired at 100,068,225 instructions/10.0068225 seconds, guard/fault 0. Screen 0, 5/8 unchanged. [Power cycle](original-boot-adc-power-cycle.md) · [Timer cycle](original-boot-adc-trigger-cycle.md). Cleaned duplicate dumps of 3849841 bytes per task; owned Docker removed.

bw544: Model/board unchanged, 20-second observation, 139,370,233 instructions/20.178 seconds, guard/fault 0. Original WFI followed by PC44e176, additional BLE init log, frame 0. Existing first-screen run included virtual touch/UART peer inputs, not applied to this runner. Next verify state and connect wire input. [Extended observation](original-boot-main-extended-observation.md). Cleaned duplicate 3849841 bytes; owned Docker removed; 5/8 unchanged.

bw545: Verified 29 connected original active tasks; currently IDLE. UI/display queues waiting empty and renderer waiting for notification. UART0 on/TX13/RX0, touch consumption 0, GPU off. Next connect virtual GPIO/UART inputs without forced PC/TCB changes. [Readiness](original-boot-main-input-readiness.md). Cleaned duplicate 3849841 bytes, preserved key SRAM evidence, owned Docker removed, 5/8 unchanged.

bw547: **Original boot→main→virtual touch/UART wire→original UI/render→completed 576×288 screen succeeded.** Final 02 first nonuniform frame/raw 165888 bytes/guest SRAM exact, PNG directly inspected, full canonical boot/main identical, guard/fault 0. CPU/time/full RAM exact before/after HP cadence. [First screen](original-boot-first-screen.md). OB06 complete 6/8=75%; repetition/negative checks, reproduction CLI, and final audit incomplete. Preserved 01 RAM reuse mismatch after 500ms. Cleaned duplicates totaling 22379746 bytes; two owned Docker containers removed.

bw548–549: Pinned profile/reproduction CLI and 14 boundary tests, normal 30-condition audit each. Two cold runs under same configuration produced completed frame SHA exact; CPU/time differences disclosed. Verified unknown marker original strict read boundary 29 conditions and two host rejections for corrupt/truncated input. [Reproduction CLI](original-boot-reproduction.md) · [Repetition/rejection](original-boot-repeat-and-rejection.md). OB07 complete 7/8=87.5%; final full audit remained. Cleaned bw549 duplicates 15189587 bytes; owned Docker removed.

Final bw550: **All eight original conditions complete.** [Final audit](original-boot-completion-audit.md) · [Reproduction CLI](original-boot-reproduction.md). Two identical final cold runs/completed frame SHA exact, 30 conditions each, unsupported original boundary 29 conditions, host corruption rejections 2, 14 tests, current comparison of 116 folders/178 owned journals passed. Owned containers/inspection build duplicates remaining 0. This is distinct from actual Boot ROM/full chipset precision/physical certification and does not automatically activate a subsequent Goal. Earlier stage numbers are historical. Canonical private original-boot-final-audit-bw550-01/report.json.
