# VDDF trim reconfiguration by main after original boot

bw-0541. State inheritance on the same stock 2.4 boot→main board was analyzed. Original ARM runs without physical access or firmware changes.

## Cause confirmed

The previous run stopped at main PC 0x5c1b40 writing VREFGEN4 (0x4002004c)=0x1fefac. The model rejected all writes after the first calibration when Applied=true.

Read-only post-stop observation of the same model confirmed before=0x1fefb6 (low7=54), proposed=0x1fefac (low7=44), XOR=0x1a, writes 1/reads 4, buck active, and memory setup 2. The saved reference at original main SRAM 0x20076c34 was also 54. CPU, events, and boot globals were exact before/after observation; owner was not changed by address guessing.

Original main 0x5c1abc..0x5c1b66 checks its own saved-reference flag and buck ACT, calculating temperature-range correction 10 or 0 and GPU boost 15. It subtracts or adds correction from the saved reference, clamps the range, and writes only low7 using BFI. In this profile, after boot 64→54, main saves 54 as its own reference and calculates 44. Guest cache is not overwritten with 64 and hardware is not reset cold.

Public Ambiq HAL am_hal_pwrctrl.c 2396..2404 stores current VREFGEN4 when each image's g_bOrigTrimsStored is false. am_hal_spotmgr_pcm2_0.c 166..320 and GPU/SDIO paths repeatedly adjust/restore the same low7. DFP Apollo510 VREFGEN4 and TVRGFVREFTRIM[6:0] are read-write. Thus rejecting a second write was an excessive existing-model restriction, not a hardware contract.

## Change and verification

The first cold write retains existing original-value/correction/read-witness checks. After application, 32-bit writes preserving bits 31:7 are allowed while buck active, memory setup 2, and existing read witness remain. Analog voltage effects, settling time, and power accuracy are not modeled.

A new ARM reproduction was rejected at the actual second trim before the change. Eleven conditions passed afterward: initial normal/incorrect field/not ready/stuck-off response/same-value repetition/partial width/disabled option, main 54→44, all 128 low7 values, same value three times, and rejection of other fields after initial application. Private simulator/warm-vddf-arm-{red,green}-bw541-01/report.json is retained. Twelve ELFs totaling 402,976 bytes were cleaned up and each owned container confirmed removed.

Guest boot/main full bytes in the read-observation native matched canonical. Duplicate dumps totaling 3,849,841 bytes were cleaned up. Analysis, original input SHA, commands, frozen model, logs, and comparison results remain.

## Progress

Original boot→main native with the corrected model executed 72,069,245 instructions. At virtual 7.207 seconds it stopped at shared-power write 0x40021004=0x2000 at PC 0x494d78. Before 0/XOR 0x2000 indicates ADC powered-off→on request. VDDF passed normally with writes 2/current 44. Code/system faults 0, screens 0. Additional duplicate dumps totaling 3,849,841 bytes and the owned container were cleaned up. Display and OB06 remain incomplete; overall 5/8=62.5%. This document does not guarantee physical boot, recovery, or voltage safety.

Evidence: private simulator/original-boot-warm-vddf-state-native-bw541-01/state-proof.json, warm-vddf-source-bw541-01/source-proof.json, warm-vddf-model-bw541-01/model.patch.
