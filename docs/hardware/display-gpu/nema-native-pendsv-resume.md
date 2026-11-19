# Original M55 PendSV save/restore and caller resumption

Later bw267 verified the [original blocking wait and delayed IRQ wake](nema-native-blocking-wake.md) in a configured caller. The following records the earlier immediate-completion path.

Task `bw-0266` combined [full RAM collection](../../firmware/original-main-full-memory.md) with [original IRQ integration](nema-native-irq-completion.md).

On stock 2.4, stock 2.3, and Faceclaw 38, execution reached **original draw → diagnostic GPU → IRQ28 → original PendSV save, task selection, and restore → actual exception return → submit return → original completion wait return**. This is an explicit PSP caller test using collected kernel RAM, not the result of resuming the original main at its stopped point.

## Context setup

The existing runner's opt-in `--kernel-context` is used with `--reference-gpu --live-draw --completion-irq`. `tools/nema_kernel_context.py` verifies per-image full RAM, public core diagnostics, and task graph inspection hashes. Stock and CFW snapshots are not mixed.

The full 3.5 MiB SRAM and ITCM are used; initial RAM changes are only the existing test ring table's 20 bytes and the 4-byte Nema context pointer. The Nema pointer explicitly retains `0x21001000` from the existing draw fixture. Kernel globals, current TCB, and other task stacks are not filled with success values or zeros as substitutes.

The caller starts at the current `ble_wsf` PSP value and within its stack range. It does not resume the registers or execution point of the originally stopped function. General/FPU caller inputs are values from the existing draw fixture. MSP uses OtherSP from the original capture. Actual ARM instructions in the guest bootstrap set PSP, CONTROL, PSPLIM, and MSPLIM, and record MRS results in WORK. Stack limits are explicit test inputs; this does not mean hidden core state was restored unchanged.

Permitted guest writes are WORK, two declared stack ranges, limited kernel words found in the original selector, and the existing two IRQ publication words. The current task's 16-byte stack canary is excluded. Other SRAM changes are failures, and the 3 MiB System SRAM is also compared before and after. As the memory hook observes post-access, absence of side effects in failed runs is not claimed.

## Original code execution results

| Item | Final three images |
| --- | --- |
| Bootstrap MRS | Matches declared PSP, MSP, CONTROL=6, both limits, and current SP |
| Original draw/submit/wait | All markers 1..7 complete |
| Actual IRQ28 / PendSV | 1 each |
| Original task selector / port return | 1 each |
| Selected task | Existing `ble_wsf`, priority 49 |
| Actual EXC_RETURN | `0xffffffac` |
| Final state | IPSR=0, PSP selected, PSP and MSP restored |
| Completion ID / semaphore | `8 / 1` |
| Original completion wait | Return value 0, descriptor ID released to `0xffffffff` |
| Architecture fault | CFSR=0, HFSR=0 |
| Actual framebuffer | Matches character A bytes from previous verification |

The original PendSV actually updated the current TCB's saved-SP word. The saved pointer was checked to be inside the declared task stack and the port observation to match the final TCB. Since the running stack is reused afterward, the entire saved frame in final RAM is not treated as a still-valid checkpoint.

The Thread/PSP and extended-FP format of EXC_RETURN and actual Thread resumption were checked together. Bit meanings follow the [Armv8-M Exception Model User Guide](https://documentation-service.arm.com/static/64c7832738511951cb7a246e). Initial S16..S31 values were all 0 in this input. This is not extended to verification of preservation across arbitrary nonzero high-FP/vector states.

## Problems found and fixes

1. The first full-RAM merge omitted the existing test Nema context pointer. Original bind stopped at the guard while trying to write to the actual context. Only the declared pointer overlay was retained, without allowing unrestricted writes.
2. The raw glyph descriptor now appeared on the actual task stack instead of WORK. The exact PC, address, raw flag, and glyph conditions of the existing ITCM exception were retained, and the declared task stack was added to the descriptor ownership range.
3. A host CONTROL setter problem meant PSP selection did not actually change, causing an incorrect saved SP and exception fault. A separate runtime probe without a guest reproduced `IsUsingProcessSP=false` even with CONTROL=6. The test switched to guest MSR and verified MRS and actual resumption. `SeedRegister` now rejects host-style PSP selection.
4. The initial test left PendSV priority at its default, so it preempted inside the GPU IRQ handler. Although the call marker returned, EXC_RETURN Mode was Handler. Two ORRs in the original port's SHPR3 initialization that lower PendSV/SysTick priority were identified in each image, and the configuration was matched. Final priorities are PendSV=255 and GPU IRQ=64, and normal Thread/PSP return was confirmed. The earlier result that passed the weaker check is not adopted as final evidence.

The current board's SysTick is disabled. Nor has the complete NVIC, timer, and peripheral state been restored from snapshots. These differences are explicit, and only the limited caller path is verified.

## Controls and evidence

The existing IRQ profile without context still stops at `rtos-context-required` and does not write the submit completion marker. The default profile without IRQ matches the entire existing WORK, and the existing six-call caller binary is byte-identical. Rejection of host CONTROL PSP selection was also confirmed in a separate runtime API probe.

Under `simulator/` outside Git:

- `nema-native-kernel-resume-01`, `-02`, `-03`: failures from missing Nema pointer, descriptor range, and incorrect host stack selection, respectively.
- `nema-native-kernel-resume-04/stock24`, `nema-native-kernel-peers-01/{stock23,cfw}`: intermediate results that returned after MSR switching but had incorrect PendSV priority. Original reports were preserved.
- **`nema-native-kernel-final-01/stock24`**, **`nema-native-kernel-final-peers-01/{stock23,cfw}`**: final three runs.
- **`nema-kernel-missing-context-control-01/stock24`**, **`nema-kernel-default-regression-01/stock24`**: final protection boundary and default regression.
- `m55-host-control-sp-probe-01`: type import failure. `-02`: reproduced actual host setter behavior. Neither executed a guest.
- `m55-host-control-guard-01`: rejected incorrect host selection before modification, with no guest execution.
- **`nema-native-kernel-verification-01`**: **235 checks passed** by `tools/audit_nema_kernel_resume.py`. It checked the final five runs, original source and inputs, SRAM boundaries, actual pixels, bootstrap, resumption, and limits of intermediate results. The audit did not rerun native execution.

This work preserves 11 native G2 ARM function runs (five final, six during development) and three guest-free API probes. Python compilation and 17 existing native contract unit tests also passed.

## Next boundary

This time the same task was selected again, and the completion IRQ arrived first so the wait returned immediately. **Switching to another task, semaphore blocking → wake, and the full main's natural UI path are unverified.** The next step is to verify with an explicit test event the path where the original wait actually enters a waiting state and then wakes on completion IRQ. The full main's SPI, external font bank, 576×288 screen, and web installation/recovery readiness remain in scope.

The overall completion conditions remain **13/29=44.8%, scope v2**. No physical glasses or case access, firmware writes, or external publication occurred.
