# STIMER Interrupt Storage Model

Work bw-0154. Following [address identification](stimer-interrupt-contract.md), the explicit digital storage portion of STMINTEN/STAT/CLR/SET was implemented. Counter, compare/capture events, and NVIC delivery are not yet present.

`BlackwallStimerInterruptStorage` requires explicit `source-reset-storage`. It initializes enable/status to 0 and accepts only the 13 defined bits. Enable stores; SET ORs status; CLR removes corresponding status bits. Direct status writes allow only 0 used by public HAL initialization; other direct assignments remain unsupported. Set/clear alias reads are not allowed. `Pending` is logical AND of enable and status, not an actual NVIC line or ISR execution.

An optional `IBlackwallStimer` was added as the last argument to the existing startup fixture. If unselected, the existing strict boundary remains. Even when selected, only 32-bit operations on four owned addresses are delegated; byte/word/quad, reserved, and invalid values are blocked by the existing guard. Addresses do not overlap RTC.

The fixture owns model lifetime and delegates `Reset()`. Initial implementation missed that delegation; after independent reading review identified it, unit03 reproduced the failure and it was fixed. unit04 passed 27 checks, including initialization of configuration, diagnostics, and Pending by fixture reset. Model reset is not evidence of physical reset.

## Original execution and verification

Original bundles/raw mains were repinned and verified, retaining initial fills and execution policy. Only the core prefix of pinned strict source was replaced with current source and an adapter added; other model parts were preserved. Only board selection and runtime observation output were added. No guest branch, return, or instruction changes occurred.

First main01 failed result collection because observation code needed the `sysbus.guard` node instead of `guard`. main02 corrected only that path and confirmed one enable read/write each in three originals, Enable=1, Status=0, Pending=false. Next was STCFG (40008800) read; unselected control was blocked at existing STMINTEN (40008900) read. After Reset delegation fix, four current-source main03 conditions and 44 RTC regression02 checks all passed. Final source, observations, originals, and existing boundaries were compared in 95 saved audit02 checks. Earlier execution and failure logs remain.

The next boundary is STCFG source/reset/clock/compare/counter contract. Interrupt storage is not generalized to complete STIMER or time progression. Enabling alone does not mean an actual timer interrupt occurred. This starts at existing main reset; ROM/full boot, app loop, and display remain incomplete.

Private simulator evidence paths: `stimer-interrupt-contract-01`, `stimer-interrupt-unit-01~04`, `stimer-interrupt-main-01~03`, `rtc-adapter-stimer-regression-01~02`, and `stimer-interrupt-verification-01~02`. No physical connection, RAM payload, OTA, permanent write, or Astra execution occurred. Product completion is 13/29 (44.8%). An agent inheriting the parent model performed a reading review; exact model ID, separate-family review, and an unavailable transcript archive audit are not claimed complete.
