# GAF Delay Function and Virtual CPU Time Contract

bw-0427. **The original ARM's 5 µs request used at least 811 instructions and 81.1 virtual µs under the current 10 MIPS profile.** Requested units cannot be equated with time consumed by the emulator. Original code, WDT, timeout repetitions, and CPU execution rate were not changed. E05 normal GAF calculation and completion of initialization remain incomplete.

## Actual original path

In pinned stock 2.4 main, the original wait loop at `0x555976` queries up to 200,000 times and calls a 5 µs callback. The actual callback is `0x4b2f9e → 0x495e88 → ITCM 0x40`. The observed high-mode path is:

| Stage | Original/observed value |
| --- | --- |
| Request and caller LR | 5 µs, `0x553615` |
| Initial conversion | 5×32=160 |
| Mode field read | Value 2 of `(0x40021000 >>3)&3` |
| Original float constants | 250.0 / 96.0 |
| ITCM argument after correction | `trunc(160×250/96)−24=392` |
| ITCM code executed | `subs r0,#1; bne 0x40; bx lr` |
| ITCM instruction count | 392×2+1=785 |
| Minimum path including callback, HAL, return | 2+23+785+1=811 instructions |
| Current virtual time | 811/10 MIPS=81.1 µs |

Five of seven complete 5 µs call samples took 811 instructions and 81.1 µs. The others took 1,008 and 1,378 instructions. This observation did not establish IRQ/task causation for the additional instructions, so those two values are not treated as pure delay-function cost.

## HAL source and time interpretation

Pinned [Ambiq HAL utils](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_utils.c) specifies the same three-instruction ITCM loop and a correction of three CPU cycles per iteration. It distinguishes LP 96 MHz from HP 192/250 MHz, using a 250/96 ratio and 24-iteration correction in HP. This agrees with actual binary constants and observed arguments. The source's cycle description is not a physical-device measurement.

The current Renode board converts instruction count to virtual time with `PerformanceInMips:10`. This is not the same contract as HAL cycle correction, and the current model's high-mode state value does not change actual CPU execution rate. Physical G2 clock, per-instruction cycles, and cache/branch costs were not verified. There is also insufficient basis to substitute 250 MIPS directly for 250 MHz.

At the current minimum path, 200,000 calls of 5 µs alone take 162,200,000 instructions and 16.22 virtual seconds. This excludes SPI, polling, RTOS, and other delay calls. It is not used as total timeout time or general proof that the watchdog comes first. Whether another task restarts WDT is separate. However, citing `5µs×200,000=1 second` as current board execution time would be incorrect.

## Observation scope and failures

An observer was added only to a pinned 500 ms run after ATT. The first attempt placed a breakpoint on the ITCM loop itself at `0x40` and ended at the 180-second host limit without collecting delay results. CPU activity was observed, but increased cost could not be separated from the engine's low-address hook effect, so the cause is not established.

The second observed arguments and ITCM bytes at original BL call site `0x495ed2`, without replacing original call/return. It did not call `SyncTime` or change PC/SP/TCB. The pinned run had 0 guard/fault/memory violations, 0 calculations, and 362 busy reads. The 363 loop entries include the last iteration whose read had not finished and must not be confused with busy reads.

The 256-row buffer also collected intermediate SPI delay calls and overflowed around the eighth poll. Only the **seven preceding complete 5 µs calls** are analyzed; all 16 or later history are not claimed verified. The full 32-byte ITCM sample also contains other unused code and A5 padding. Only the first six called bytes were used for loop semantics. The same literal six bytes exist at main `0x7bf54f`, but this is not the result of decoding the entire initialization stream.

Four SRAM snapshots (initial, connection, ATT, final), existing full result JSON, final general registers, cumulative instruction count, and virtual times at the start/end of 500 ms were exact before and after adding observation. Host cost of the observed run increased; it is not reported as a performance improvement or general benchmark. This equivalence is not extended to every observer.

## Verification and next work

Twenty-two saved audits and three counterexamples with wrong arguments, virtual time forged as 5 µs, and wrong caller passed. The HAL file was verified with Git blob and SHA256 from the pinned GitHub tree. Proprietary main/SRAM and failure logs are preserved outside Git in `gaf-delay-clock-native-01..02`; source and audits are in `gaf-delay-clock-research-01`.

Next, preserve the existing 10 MIPS baseline and first independently test a **separate functional-verification CPU time profile** derived from the HAL cycle contract. Compare delay samples, RTOS/STIMER, and WDT together before connecting it to the original timeout path. Do not reduce instruction counts or disable the watchdog to produce a timeout. Such a profile is not chipset cycle accuracy or physical timing certification either.

All 16 conditions/states and 8/16=50.0% remain. No physical device access, writes, subagents, or external publication occurred.
