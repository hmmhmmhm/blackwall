# Application broadcast and refresh boundary after UI callback

bw-0449. The bw448 HP-interval run confirmed original app 1 initialization and callback return but observed no draw within the next 100 ms. Reanalysis of the saved run found it was then inside another app callback before the refresh wait. Overall scope remains 10/16=62.5%.

## Original subsequent calls

UI continuation at `0x4456ec` publishes active app-id, then at `0x4456f6` calls `0x4439a4(2, active-app-id)`. This function iterates 52 registry rows and calls a type 2 callback when descriptor+11 byte is 1, callback (+8) is nonzero, and descriptor app-id differs from active app-id. The product meaning of the flag is not established from its number. “Broadcast” here means the confirmed original traversal.

Callback arguments are `[2,0,0,current-context[0x20]]`. Original `BLX ip` is `0x4439fa`, continuation `0x4439fc`. After traversal UI continuation is `0x4456fa`.

In bw448's final snapshot:

- Original dispatch's 24-byte frame and callback's 32-byte frame, actual saved LR, and caller BL/BLX were compared.
- Dispatch-preserved index 15, table `0x20067f80`, and active app-id 1 were confirmed.
- Row 15 is app-id 3, callback `0x4647d4`, descriptor `0x20005c44`, flag byte 1.
- Actual arguments saved in callback are `[2,0,0,0x20299a20]`, matching original context+0x20.

Thus the earlier 100 ms cannot be described as an idle wait in which refresh did no work after UI callback. Original code was initializing another registered app. The user-facing feature name of app-id 3 or completed initialization of all 52 apps cannot be claimed from this snapshot alone.

## Next execution contract

Reuse legitimate reset → touch → virtual peer ACK → HP interval → app 1 callback return. New observer stores at most 128 rows at original broadcast BLX/continuation, recording index, table, callback target, r0–r3, SP/LR, TCB/xPSR, and time. It does not change code, PC, TCB, branches, readiness, or device model.

This stage is a separate phase targeting terminal PC `0x4456fa`, with at most 1000 ms virtual and 30 seconds host. It checks calls/returns for 52 source-confirmed entries. If phase returns normally, observe first actual submit within a subsequent maximum 100 ms. Do not resume an aborted machine. Existing HP profile's unverified uniform instruction rate and physical timing limits remain.

## First observation and focused candidate

First observation paired actual callbacks and continuations for indices 2, 7, and 15, and entered index 16 callback but ended before its return. Virtual progress 159.796 ms was below configured 1000 ms, interpreted as host 30-second limit. However, pause state immediately before termination and condition-specific termination reason were not preserved as independent fields, so the cause cannot be established from a single measurement. Do not report firmware timeout or an infinite callback loop. CPU fault, strict access, and memory-protection violations were 0.

Existing layout observer's root samples hit their cap of 64 and marked overflow. This flag is not hidden and observation is not claimed complete. Seven new broadcast call/return samples were saved without overflow.

The focused fresh candidate does not install three already verified recursive-entry, root-pass, and layout-epilogue observation points from the start. It removes no other work/observer hooks and retains original device/protection/time inputs and host/virtual limits. Broadcast, app initialization, UI return, and draw/submit/frame observation remain. Scheduling neutrality or quantitative performance improvement of this observation change is not claimed.

## Broadcast completion in focused run

Applying callback, descriptor, flag, and active-app exclusion conditions to the 52-entry registry yields indices `2,7,15,16,19,20,33,36,38,39`. Twenty actual BLX/continuation samples exactly matched these ten targets. Each callback had r0=2, r1/r2=0, r3=context[0x20], original SP/TCB and Thread mode, and returned R0=0.

Traversal actually returned to UI continuation `0x4456fa`. First-entry and exit SP matched; current TCB was original `ui_task`. Nominal virtual progress for the phase was 234.091 ms. Initial original reset → UI dispatch SRAM, main, device model, and board were byte-identical to the previous HP candidate. UI observation configuration differs, so subsequent full-execution exactness or performance gain is not claimed.

## Next boundary is sensor_hub GAF request

After broadcast return, the normally resumed candidate aborted about 10.9 ms later on IOM4 `0x40054120` access at original store PC `0x58236c`. The single original guard was preserved and the aborted machine was not resumed. CPU faults and memory-protection violations were 0.

Actual current task in the linked RTOS graph was `sensor_hub` (priority 41), so this cannot be interpreted solely as blockage in UI callback follow-up. Original GAF caller `0x554966` puts r1=2 and calls helper `0x55405c` at `0x55496a`. Helper-saved r1=2 and LR=`0x55496f` were compared in actual sensor stack. Helper prepares an address 4, length 1 write. Last command register value was `0x401`, TX word `0x0204007c` (bytes `7c 00 04 02`).

Current candidate board enables GAF configuration only and does not select `gafOnDemandControl`. This checkpoint connects to the existing unsupported **GAF request 2 execution boundary**. It is not grounds to add a new successful GPU/screen API response or arbitrary sensor-computation completion. Exact peer reject operation/value were not collected in this final summary, so finer internal failure conditions are not established beyond original request/guard boundary.

Draw, target, submit, ring submit, display producer, and frame wrapper were all called zero times. Screen pixels and full E09 completion remain unverified. Next separately investigate verified GAF fault-control profile and actual sensor/renderer scheduling dependencies. Fault-scenario progress is not promoted to normal GAF calculation or required-service completion.

## Verification and material

Final saved audit's 59 checks covered source/actual stack binding, all ten target calls/returns, original UI return, device/input prefix identity, actual sensor task/MMIO/request boundary, preservation of first failed observation and overflow, and cleanup of two containers. Focused observation overflow was 0. All proprietary material is outside Git in `simulator/ui-refresh-research-01`, `ui-refresh-native-01/02`, hashed by `simulator/ui-refresh-manifest.json`.

Overall acceptance is 10/16=62.5%. No physical devices, persistent writes, subagents, or external publication.
