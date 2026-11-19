# Research on Reusing Existing Emulators and Chipset Material

Purpose: Determine whether actual Cortex-M55 and peripheral models can be reused to reduce one-register-at-a-time reimplementation. After this initial investigation, official Renode and .NET 8 were installed separately and 32 register locations compared by compilation. Execution failed at the CoreCLR stage; see the [subsequent runtime record](renode-runtime-readiness.md). An engine switch was undecided. Later, [M55 execution and M4F control tests](renode-m55-probe.md) passed on Linux ARM64. Distinguish the initial source investigation's unverified-execution statements from those later results.

## Candidates actually found

| Candidate | Reusable assets confirmed | Remaining differences |
| --- | --- | --- |
| Renode | Cortex-M55 support, Apollo4 peripheral source and platform tests | Apollo510B and G2 board support unverified |
| QEMU | mps3-an547 board using Cortex-M55 | This is an Arm MPS3 model and does not provide Apollo510 peripherals |
| Ambiq HAL/CMSIS | Apollo510 addresses, bitfields, and initialization code | Exact G2 SDK revision, device calibration, and external component connections remain separate |

[Renode 1.16.1 release](https://github.com/renode/renode/releases/tag/v1.16.1) states Cortex-M55, FPv5, and initial MVE support. This does not mean all M55 features are accurate or G2 execution succeeded. [QEMU board documentation](https://www.qemu.org/docs/master/system/arm/mps2.html) identifies mps3-an547's M55. Loading a G2 image into an existing MPS3 board does not make it a G2.

The public HAL is already used as evidence for the current model. But extracting addresses and reset values from headers alone does not implement interrupts, FIFO, DMA, timing, or power behavior. The next task is to prioritize existing peripheral models that support these behaviors.

## Actual Renode source inspection

Upstream pinned at investigation time:

- renode/renode: `d982ac6c12ca3d13cfcfa2422f20fbd89272abf3`
- renode/renode-infrastructure: `042a58285ee91453f99d31f19e8aa140102ec540`
- The Renode tree's src/Infrastructure gitlink was confirmed to match the second commit.
- Eight source/license files were retrieved and Git blob SHA-1 and SHA-256 checked. This was not execution or build verification.

The [Apollo4 platform](https://github.com/renode/renode/blob/d982ac6c12ca3d13cfcfa2422f20fbd89272abf3/platforms/cpus/ambiq-apollo4.repl) contains GPIO, ADC, IO Master, RTC, timer/STIMER, PL011 UART, watchdog, power controller, and more. Its selected CPU is M4F. Being able to select an M55 is separate from being able to use this platform directly as Apollo510B. No platform named Apollo510/510B was found in the tree.

Some candidate base addresses overlap current Apollo510 definitions, for example STIMER 0x40008800, UART2 0x4001e000, power 0x40021000, and watchdog 0x40024000. However, **matching addresses are not evidence of behavioral compatibility**.

Specific differences were also identified. Apollo4 [SystemTimer source](https://github.com/renode/renode-infrastructure/blob/042a58285ee91453f99d31f19e8aa140102ec540/src/Emulator/Peripherals/Peripherals/Timers/AmbiqApollo4_SystemTimer.cs) calls offset 0x58 NVRAM2, while the public Apollo510 header defines the same location as HALSTATES. The Apollo4 platform also marks the MCUCTRL range SilenceRange and replaces some boot-ROM functions with virtual code. Taking this unchanged to pass G2's unimplemented boundaries would change the meaning of validation. Renode and infrastructure root licenses are MIT; separately retain and review licenses for actual imported files and dependencies. No source was copied into the project at that time.

## Recommended follow-up validation

1. Verify CPU, exceptions, and SysTick/NVIC using independent code on Renode M55 with minimal memory.
2. Compare Apollo4 models block by block against Apollo510 register, IRQ, and clock definitions, starting with potentially reusable components such as UART, timer, and watchdog.
3. Compare with current pinned firmware, virtual inputs, and stop boundaries to assess whether a broader scope executes correctly.
4. Decide whether to retain the engine, reuse parts, or migrate to Renode based on that evidence. Do not decide migration from source availability alone.

Development acceleration through reuse was an inference. Its magnitude, G2 boot, and display success had not yet been measured or demonstrated. Virtual hardware passing reset/voltage conditions does not establish physical installation or recovery safety. Actual glasses were not accessed.

The investigated original tree, source, and hash manifest are retained outside Git in `Blackwall/simulator/emulator-reuse-research-01/`.
