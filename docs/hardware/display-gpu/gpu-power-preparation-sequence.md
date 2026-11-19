# Limited model of GPU power preparation sequence

Status: limited verification completed for native model, ten synthetic conditions, four existing-behavior regressions, and six original main combinations. This is not full boot, GPU execution, or actual power verification.

## Evidence and supported branch

`am_hal_spotmgr_pcm2_0_gpu_on_sequence`, short macros in `am_hal_pwrctrl.h`, and public register masks from Ambiq HAL `61b293a49db34030c545f99101f7ebf6a3050314` were compared with actual stock 2.4 instructions. Existing original execution stopped at the first CORELDO calibration write. The new model supports one connected preparation cycle after that point.

Scope is the GPU HP branch of the PCM2 path observed under current synthetic initial values. Additional PCM1.0/1.1 calibration, different B0 MEMLDO restore value, GPU LP/off, and repeated lifecycles are unsupported. Virtual chip revision/initial values are not verified to match the physical G2.

1. Increase CORELDO active trim by 12, saturating at 1023.
2. Store MEMLDO active trim=5.
3. Set PWRSW1 bits 29, 28, 31, 30 in order.
4. Set TON2 low/high=6, TON4 low/high=5, TON7 low=13, TON6 high=19.
5. Clear the four PWRSW1 bits in order.
6. Restore starting CORELDO trim and MEMLDO trim=1.

Total 18 writes. Bits outside fields are preserved. CORELDO saturation calculation is source-backed, but current runtime test is synthetic trim 973→985→973; saturation boundary values were not separately execution-tested. GPU enable request is not part of this preparation sequence.

## Execution policy

`--gpu-power-preparation` is explicitly selected with GFX selection, nominal clock response, and HFRC force control. Buck ACT, VDDF calibration completion, GPU source 1/request 3, MCU HP state, and HFRC/HFRC2 force must be ready before the first write. After starting, incorrect order or values for owned registers stop instead of bypassing to another storage model. Repeating the cycle after one completion is also unsupported and stops.

Other synthetic startup-model initialization remains until start. This policy describes the current virtual model's supported scope, not a claim hardware rejects every other sequence. Voltage, rail shorting effects, settling delay, power, and GPU commands are not implemented. Reported original trim restoration is restoration of synthetic control fields, not evidence of physical voltage recovery.

## Verification material

Private `simulator/gpu-preparation-native-guard-01/report.json` passed ten conditions. One completion case checked completion sentinel and field restoration. Nine rejection cases checked missing GFX/HFRC prerequisites, wrong first value/order/MEM trim/rail bit/access width, repetition, and option disabled, confirming completion writes did not execute after the first unsupported access.

`gpu-preparation-main-stock24-lp-01/report.json` completed 18 stages in actual main and restored CORELDO=0x6d3cd, MEMLDO=0x207c0741, PWRSW1=0x11000, then stopped at PC0x494d78 attempting GPU bit 18 set (0x40000) in PWRCTRL.DEVPWREN (0x40021004). Power response to this request and the GPU engine are unsupported.

Python stops at the earlier SHCSR/MPU boundary. It is not described as having the same endpoint or full execution equivalence as native. Full main app loop and integrated screen remain incomplete. No physical access, OTA, MRAM modification, or external publication.

## Final evidence

- `gpu-preparation-main-comparison-01/report.json`: six combinations, two stock versions and Faceclaw × LP/HP, passed. Native 18 stages, values/read/write counts for seven control fields, and next GPU enable request were checked. Stock 2.3/CFW PC=0x488e90, stock 2.4 PC=0x494d78. First stock 2.4 LP result was reused after hash/source/option checks.
- `gpu-preparation-native-regression-01/report.json`: four conditions passed for default unsupported access, existing no-ack clock, HFRC force, and GPU HP selection.
- `gpu-preparation-source-audit-01/report.json`: source hash, field masks, C structure offset compilation, boost constants, and rail macro order. It does not automatically prove semantic equivalence of the entire HAL.
- `gpu-preparation-verification-01/header-origin.json`: public `am_hal_pwrctrl.h` compared with pinned GitHub commit tree/blob to confirm local copy.
- `gpu-preparation-verification-01/main-prefix-audit.json`: static disassembly of actual preparation code for three inputs.
- `gpu-preparation-verification-01/comparison-regression.log`: one optional-model null/absent handling regression passed. Missing CLI prerequisites were also rejected before reading inputs.

Comparator explicitly checks native's extra cache sweep, buck reads 3, MCU reads 4, MISC controls 2, clock read 1, and different endpoint relative to Python. Python's SHCSR/MPU limitation remains.

For reproduction add `--gpu-power-preparation` to the existing main comparison command. Use a new output path to preserve earlier evidence. Physical-device installability judgment remains false.
