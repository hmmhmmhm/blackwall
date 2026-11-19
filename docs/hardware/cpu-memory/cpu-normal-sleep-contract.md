# Original CPU Normal-Sleep Preparation Contract

bw-0311. Verified three main/SRAM/GPR inputs and saved audits from bw310, then analyzed original ARM from the current CPU-power read **up to just before WFI**. Peripheral models and the natural M55 execution endpoint remained unchanged. Overall acceptance was **13/29 = 44.8%, scope v2**.

## Current caller and actual execution scope

The saved argument on the original stack is 0. Comparing BL at the actual return address and the function prologue confirmed the normal-sleep path. All three binaries share the structure. This result alone does not establish full boot, entry into an RTOS idle task, or completed display initialization.

| Input | Existing natural-main stop | WFI boundary in function-level test |
| --- | --- | --- |
| Stock 2.4 | `0x44e10c`, CPUPWRCTRL read | `0x44e174` |
| Stock 2.3 | `0x44d81c`, same | `0x44d884` |
| Faceclaw 38 | `0x44d81c`, same | `0x44d884` |

The runner is Unicorn M7. It starts from original GPR, full SRAM, and stack, supplying Thumb state and explicit MMIO/SCS fixtures. Frame-variation tests are separate inputs. Execution stops before WFI; actual sleep, interrupt wake, and subsequent scheduler behavior were not executed. Firmware instructions, branches, and return values were unchanged.

## Behaviors to model together

1. Read `PWRCTRL.CPUPWRCTRL(0x40021050)` bit 2, `SLEEPMODE`. Tested all 1,024 combinations of public mask `0x1efc`. Bit 2 divides execution into two address paths, but preparation writes in this normal-sleep section are the same. Other bits did not change the section's PC path or writes.
2. Write `PWRMODCTL.CPDLPSTATE(0xe001e300)` based on existing CPDLP configuration. All three fields in the current native frame are 0. Actual original output is **`0x11`**.
3. Clear only SLEEPDEEP in `SCB.SCR(0xe000ed10)`. Preservation of other SCR bits was tested.
4. Read `SYNC_READ(0x47ff0000)` to flush System Bus/APB writes. The pinned Ambiq header describes holding the bus until completion. Function-level 0/`0xffffffff` responses are fixtures checking that return data is unused; they do not implement actual write-order guarantees.
5. Reach the original WFI instruction. WFI was not replaced with NOP or forced return.

CPDLPSTATE differs from Apollo PWRCTRL registers. Compared RLP/ELP/CLP positions 8/4/0 and address in the pinned [CMSIS M55 header](https://github.com/ARM-software/CMSIS_6/blob/45dab712ad84f8cbbf2b7bfc089c19088507df6f/CMSIS/Core/Include/core_cm55.h) with original literals. Initial 0 is a fixture used by the existing virtual board and native frame, not a physical device reading.

## Where copying the SDK unchanged differs

Pinned [Ambiq sysctrl source](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_sysctrl.c) sets default ELP to `ELP_RET` in both normal-sleep branches. The enum at the same commit sets RET=2, so this frame would output `0x21`.

However, **the actual three binaries prepare ELP=1 and CLP=1 and write `0x11`**. Do not attribute this difference to a binary bug or specific SDK release without evidence. The SDK informs structure and meaning; original code takes priority for actual G2 ABI and behavior.

In frame variations, when existing ELP was 2 or 3 the original preserved it. If RLP=3 and CCR cache bits are enabled, the config setter returns 1 without writing CPDLPSTATE. Upper normal-sleep code does not check this result and continues SCR clear/flush/WFI preparation. Current native-frame RLP is 0; do not extend variation tests into natural-execution error-recovery evidence.

## Verification material and limits

For each input, checked 1,024 CPUPWRCTRL combinations and 96 SCR/CCR/flush/active-field variations: **3,360 original ARM scenarios** total. Compared PC paths in two SLEEPMODE groups and checked CPDLP writes, config return values, SCR updates, and flush order. This count is not boot-test count or a performance metric.

Tool: `tools/inspect_cpu_sleep_contract.py`. Ambiq C/header and power enum header were verified against Git blobs in the pinned tree. CMSIS header was compared with the existing version/commit/SHA manifest. Public SVD SHA was also pinned. Nine models were unchanged.

The next model must combine **CPUPWRCTRL reads, restricted CPDLP storage, and APB flush** for normal sleep. Do not expand scope to generic power-off, arbitrary CPU register writes, deep sleep, or successful device wake. Leave actual WFI and pending-interrupt handling to original Renode M55 execution and separately establish evidence for caller, scheduler, and display task after wake.

Final analysis is `simulator/cpu-sleep-source-02/`; frozen reproduction is `cpu-sleep-source-03/`. Reports/inspectors match byte for byte respectively; 88 Python dependencies, inputs, SDK, and results are pinned in `cpu-sleep-verification-01/manifest.json`. Source01 is preserved from before SDK enum verification was strengthened. Natural main reruns: 0.

There was no physical glasses/case access, flash, OTA, or persistent write. The goals of web installation, Faceclaw CFW, recovery boot, and integrated display remained unchanged.
