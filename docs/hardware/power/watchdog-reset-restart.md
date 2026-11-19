# Original Service Return After Watchdog Reset

bw-0426. Resume the virtual reset initiated by a natural watchdog request in original stock 2.4. Original code, branches, TCB, PC/SP, WDT configuration, clock, and GAF timeout loop are unchanged. Normal GAF calculation and full required initialization remain unsupported; this is distinct from a scenario injecting a virtual phone after stopping at the getter.

## Actual next boundary and reused models

Unchanged `watchdog-restart-native-01` resumed after reset vector and the strict guard rejected `CPDLPSTATE(0xe001e300)=0x22` write at PC `0x4956e2`. The original reconfigured WDT and restarted it three times. Faults and memory violations were 0; peer was Unreleased/0 before initialization.

The independently and originally verified CPU retention preparation and TIMER state models from bw416–417 are reused at this boundary. Only the actual compiled CPU helper and TIMER adapter portions of pinned `cpu-retention-preparation-research-01/manifest.json` are imported. Other watchdog, communications, shared IOM, memory protection, and cache models remain. The board specifies the exact original retention PC and disabled timer/audio and flush options. Since a need for original reset STAT access has not been observed, no new read is added to the startup guard.

## Execution-control deadlock diagnosis

The first extended-profile run `watchdog-restart-native-02` deadlocked on the host immediately after reset. It is not assessed as firmware return or normal wait. Actual thread stacks from .NET trace were:

- Shell thread 22: `Machine.Pause → CPU Pause → Thread.Join`.
- CPU thread 38: `ResetEntryObserver callback → Machine.Pause`.
- Master time source thread 31: `TimeHandle.WaitUntilDone`.

[Pinned Machine.Pause source](https://github.com/renode/renode-infrastructure/blob/cd4b002aac2398994c4a61a34a8b31b5700facf2/src/Emulator/Main/Core/Machine.cs) stops CPUs inside a pause lock. This is consistent with a circular wait in which the CPU observation callback enters the same pause lock while the host waits for CPU. The original loop treated transient `m.IsPaused` during reset as final completion and called host Pause; that path was corrected.

`reset_entry_pause_contract.py` exposes its owned observer's `Seen` **after** `machine.Pause()` returns. The new host loop waits for this completion signal instead of `m.IsPaused` and performs no subsequent Pause, snapshot, or resume before completion. This does not change original firmware or safety guards. Existing observer source and historical frozen audits remain preserved.

Diagnostic `dotnet-stack` ran after resolving initial permission/path issues, but its stack output was empty and is not used as evidence. The stacks above came from a ten-second thread-time trace with existing pinned dotnet-trace and Speedscope. Only that container was expanded from 512 MiB to 1 GiB for diagnosis and excluded from performance comparisons. After preserving material, the deadlocked container was explicitly terminated and launcher exit 137 recorded. No other work container was terminated.

A separate synthetic test with a 100 ms scheduling window completed under the old order too, so it did not reproduce the actual deadlock. The corrected order also completed. This is not called a failure-reproduction test or proof for every thread schedule. Evidence for the original failure is the actual original-run trace. [Microsoft diagnostics documentation](https://learn.microsoft.com/en-us/dotnet/core/diagnostics/dotnet-stack) describes this tool's scope as managed-code stack collection.

## Assessment boundary

After reinitialization, separately assess new controller session, new connection, original ATT app return, and RTC commit. Normal original GAF calculation/full initialization and physical watchdog/reset retention policies are not verified. All 16 conditions and denominator remain. No physical-device access, writes, subagents, or external publication occurred.

## Verified return result

Corrected `watchdog-restart-native-03` re-entered original reset vector/SP, passed retention configuration, and reached getter `0x5542c6`. At this boundary the peer had handled 59 initial commands of the new session with events 0. It accepted a new virtual connection; events became 1, and at original ATT time-app return `0x492ce2`, events 3, RTC commit 1, and date `2023-11-14T22:13:20.03` were confirmed. Watchdog delivery and NVIC reset each occurred once over the full interval; guards, CFSR/HFSR, and memory violations were 0. No PC/SP/TCB seeds were used.

Twenty-two saved-material audits and three semantic counterexamples for lost RTC commit, lost new session, and extra reset passed. Initial, connection, ATT, and reset-entry SRAM snapshots were all byte-exact between baseline and corrected runs. This comparison is not generalized to absence of effects for all observers or timing. Normal original GAF calculation and initialization completion remain unverified.

Overall progress remains 8/16=50.0%, with E05/E06 partial. Next, rather than adding reset variants, obtain evidence for normal E05 GAF calculation or the original failure-return path and subsequent consumption. Proprietary main/SRAM/trace and original failure logs remain outside Git in `watchdog-restart-{native-01..03,diagnostics-01,research-01}`.
