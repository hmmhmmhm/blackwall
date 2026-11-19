# Original Bootloader Initial Execution and Current Boundary

bw522–523. First profile: stock boot2.4.0.24/main2.4.0.24, Renode M55. Actual Boot ROM or physical glasses were not executed.

Initially the main code policy rejected 0x432cb2 and stopped at instruction 0. A separate boot readonly region was explicitly configured while retaining existing main/ITCM protection. Eight M55 tests passed for main writes, ITCM execution, main padding, and boot normal execution, writes, padding reads, padding execution, and truncated Thumb32.

The existing frozen first-screen memory policy also lacked the root's earlier CPU-reset I/O-route preservation fix. The existing with_memory_policy helper checked baseline SHA330182ef… and replaced only the current policy module. The native plan explicitly recorded this difference, boot binding, existing functional cache/system-control Attach, and read-only stage observation. No other functional device code was replaced.

## Actual execution evidence

- Started from original vector 410000 SP2007fb00/reset432cb3. Observed reset/C runtime/FPU/C initialization/data init/bootloader internal C main 41b862 in matching order 1…6.
- Executed 1024153 instructions and virtual 102.4153ms. The original wrote 24 ITCM bytes and passed existing execution protection.
- Code protection, system control, unsupported guard, and CFSR/HFSR errors 0. The guard counter denotes unsupported accesses; it does not mean all MMIO accesses were 0.
- All 149773 guest boot bytes after execution matched the original. Original main/boot files were referenced through readonly mounts without duplicate copies.
- Target main reset 5fbe3e, stock handoff 42dfe8, and boot manager 42e650 were not reached. The bootloader's internal C main is distinct from target application main.

Canonical private evidence: `original-boot-startup-native-bw523-01/startup-proof.json`. Currently only OB01/OB02 are complete, 2/8 (25%).

## PC40 analysis and next experiment

The last PC in the virtual 100ms budget diagnosis was ITCM40. The existing original data-init function was rerun in isolation to extract ITCM bytes absent from the earlier report. This is auxiliary analysis, not separate natural boot evidence. The original copied code at 40..47 is `subs r0,#1; bne 0x40; bx lr; bx lr`. Other A5 initialization fill is excluded from code evidence.

Boot C main first passes r0=200 to 41f9e8, which multiplies it by 1000 and calls 41d1c0. This function calculates a count using FPU operations and clock fields, then calls original ITCM40 at 41d20a. Therefore the present 100ms budget expiry is not classified as a device fault or infinite hang. The next diagnosis retains model 10MIPS and original branches, observes R0/PC order and ITCM bytes at original delay call/return, and explicitly increases the budget. It does not skip the delay or write the counter to 0.

## Post-task cleanup

After verification, 25 files totaling logical 180865 bytes were cleaned: ELF/generated seeds for eight green/one red guest fixtures and identical guest boot copies. Fixture C/linker, actual execution logs, pinned model source, rebuild argv, and seed recipe were preserved in startup-proof cleanup. All owned Docker containers were removed, and -B execution confirmed no root cache.

## Actual return from initial delay and next power boundary

bw524 retained 10MIPS/same model/original bytes and increased budgets to virtual 2 seconds/host 120 seconds. It observed r0=6399985 at original 41d20a and r0=0 on original 41d20e return. Initialization dispatch 41fa08 and board init 430536 then executed in order. Actual ITCM40..47 bytes 0138fdd170477047 matched auxiliary extraction. The host did not change counter/branch/return; 13789605 instructions and virtual 1.379 seconds executed.

The current first unsupported boundary is a request at PC41c05c to write 4-byte value 2000 to 40021004. Code protection/system control/CFSR/HFSR are 0, and execution stopped at one previous shared-power guard. Do not infer owner from register value/PC alone; check request_before/proposed XOR and owner mask/phase next. Manager/handoff/target main reset remain unreached, so progress remains 2/8.

Canonical private evidence: `original-boot-delay-native-bw524-01/frontier-proof.json`. The one-off container was removed and identical guest boot copy of 149773 bytes cleaned; original, analysis, original registers/events/model/plan were preserved.

## Shared power owner confirmed

bw525 added the existing post-stop power exporter for observation only. Original/model/board matched, and pre-stop registers/instruction count/boot globals were exact to bw524. Request before 0→proposed 2000/XOR2000 changes only ADC bit13. All UART/IOM/MSPI/OTP/CRYPTO/GPU requests/status remain 0. The ADC power request is therefore established from actual shared state and the pinned header bit, not value/PC speculation.

The current model's buck phase was off. The ADC allowance in the model actually used requires both ADCCAL==0 and BuckResponsePhase==active, so it rejects this condition. The current calibration value was not included in this observation and needs separate confirmation. Next compare boot's required initial LDO/buck state and model assumptions with SDK/original code. The host did not force phase/status or a success return.

Canonical private evidence: `original-boot-power-owner-native-bw525-01/owner-proof.json`. An unnecessary Unicorn dependency import in auxiliary code failed before execution and was changed to read only the POST constant via AST. This is distinct from a firmware native execution failure. After repeated diagnosis, owned containers were removed and identical 149773-byte guest boot copies cleaned. Original, key analysis, and reproduction inputs were preserved.

bw526: Confirmed original boot ADC automatic calibration disabled/buck off request and removed only excessive buck conditions at two ADC dispatch points. Cold 44 items/existing 20 conditions passed. After 13,789,871 original instructions and one ADC request/response, reached PC426fc4, 40004044=1 write boundary. Main/frame unreached, 2/8 unchanged. [ADC contract](original-boot-adc-cold-contract.md). Cleaned 20 ELF files totaling 676864 bytes and two identical boot dumps totaling 299546 bytes; owned Docker removed.

bw527: Separated buck conditions for HFRC/2 control and MCU mode; cold 12 items/existing 10 conditions passed. After 13,791,447 original instructions, reached 40021004=400 power-request boundary. Main/frame unreached, 2/8 unchanged. [Clock contract](original-boot-cold-clock-contract.md). Cleaned ELF/identical dumps 485465 bytes; owned Docker removed.

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
