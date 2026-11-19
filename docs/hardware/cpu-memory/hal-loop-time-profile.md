# Functional Time Profiles Derived from the HAL Loop

bw-0428. Independent tests of the original ARM HAL delay function verified LP 64 MIPS and HP 167 MIPS profiles. The default G2 board remains at 10 MIPS. A synthetic caller invoked only the stock function and observed original ITCM code. This is not verification of original main boot, RTOS time, physical clocks, or full cycle accuracy.

## Derivation and prior acceptance criteria

The loop in the pinned [Ambiq HAL](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_utils.c) is two ARM instructions and three source-calibrated CPU cycles. Based on the source's LP 96 MHz/HP 250 MHz calibration, uniform instruction execution rates were defined as 96 × 2/3 = 64 and 250 × 2/3 = 166⅔ MIPS. HP is rounded to the nearest integer, 167, for Renode input; relative rounding error is +0.2%. The values were not fitted to timeout results.

`hal_loop_time_profile.py` accepts LP/HP only and returns an explicit profile called `hal-loop-equivalent-v1`. It does not claim that every opcode has this cycle ratio. Actual branch, FPU, cache, and bus timing in particular differs.

Test inputs were 0, 1, 5, 50, and 1,000 µs. Before the first run, tolerance was fixed at `max(0.3 µs, 1% of the requested value)`. This is a comparison criterion for this functional profile, not a guarantee of physical HAL accuracy. Neither values nor tolerance were changed to fit results.

## Original ARM execution

The entire original main byte sequence is loaded as read-only material and a synthetic ARM caller invokes HAL `0x495e88`. The original six bytes at ITCM `0x40`, `subs/bne/bx`, are also compared with observed material. The ELF vector is the synthetic caller's `0x10000`, not the original G2 reset vector. Existing MMIO models provide the CPU mode value and STIMER/WDT.

| Profile | Original instruction count for a 5 µs input | Time converted from instruction count | Observed time delta |
| --- | ---: | ---: | ---: |
| Existing HP 10 MIPS | 809 | 80.9 µs | 80.9 µs |
| Separate LP 64 MIPS | 308 | 4.8125 µs | 4.75 µs |
| Separate HP 167 MIPS | 809 | about 4.8443 µs | 5 µs |

The table excludes the callback wrapper's two instructions; do not confuse it with bw427's 811 instructions. Every original HAL call returned, with zero faults and guard accesses. The same caller ELF and original main/ITCM bytes were used.

## Time quantization and preserved failure

The first HP result observed 49 µs for the 50 µs input, failing the initial criterion. That report is preserved unchanged. The CPU conversion in the [pinned Renode TimeInterval](https://github.com/renode/renode-infrastructure/blob/cd4b002aac2398994c4a61a34a8b31b5700facf2/src/Emulator/Main/Time/TimeInterval.cs) reports time only after `MIPS/gcd(MIPS,1000)` instructions accumulate. Direct execution of the conversion API also confirmed:

| MIPS | Minimum instruction batch | Minimum reported time |
| ---: | ---: | ---: |
| 10 | 1 | 100 ns |
| 64 | 8 | 125 ns |
| 167 | 167 | 1 µs |

Thus, for a 50 µs input at 167 MIPS, 8,309 instructions correspond to about 49.7545 µs, while observed time can be 49 µs. `SyncTime` was not forced. Revised observation convention v2 applies the existing tolerance to instruction-count-converted time and separately checks whether raw time agrees within the engine's reporting unit. The initial raw-time failure is also retained as a field. The tolerance is unchanged.

Original execution results before and after the HP observation convention change were exact except for the new conversion API data. Do not extend this single comparison into evidence that all observers are nonintrusive. Do not claim precise measurement of HP time differences of 1 µs or less using raw timestamps alone.

## Independent peripheral time

For each profile, the CPU continued spinning after caller completion for a virtual 200 ms. STIMER produced 6,553 ticks at 32,768 Hz; the WDT counter was 3 at 16 Hz, with one interrupt event and `pending=true`. The WDT interrupt mask was off, so `IRQ=false`, and RESEN was not used. Watchdog reset deadlines and RTOS preemption were not tested. Execution of more than one million CPU instructions was also checked.

At the existing 10 MIPS only the HAL timing criterion failed; peripheral time was the same. The LP and HP observation-convention-v2 profiles passed delay, quantization, and peripheral-time checks. Two earlier linker-syntax and device-name selection failures are classified separately as failures before ARM execution.

Passed 31 saved audits and three counterexamples for incorrect execution rate, timer count, and inconsistent timestamps. Three pinned Renode source files were also verified by Git blob and SHA-256. Original firmware and execution artifacts are preserved outside Git in `hal-loop-time-{baseline-01..03,derived-lp-01,derived-hp-01..02,research-01}`.

## Next boundary

The next original-main test is an **explicit phase-specific diagnostic profile** that preserves the existing early boot/ATT section and applies HP 167 MIPS only after confirming actual HAL mode field 2 at a whole-machine pause. It does not change original timeout/return/TCB/SP or WDT. The entire early boot LP → HP transition has not been verified with the new profile, so it is not automatically adopted as the default board.

E05/E06, normal GAF calculation, and full initialization remain incomplete; the overall rate at that point was 8/16 = 50.0%. There was no physical device access, writing, subagent invocation, or external publication.
