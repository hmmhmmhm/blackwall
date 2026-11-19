# Post-initialization controller version query in sustained execution

bw496. Original execution path is preserved while post-initialization HCI version query is handled as an explicit virtual-device contract. This is not physical identity verification.

## Stop cause confirmed

Saved `sustained-em9305-inspection-native-01/stock24` stopped 8.160403 seconds post-screen at GPIO117 ready `0x40010410`, original PC `0x501676`. It was not UART. Pin117 setting 0x93, CS low, startup 59 commands/60 responses complete, peer Complete/ReadyLevel=-1.

Comparing original SPI writer R10=0x20067868, R8=4, offset=0 and full SRAM shows next transmission `01011000`. Existing peer `pending_hex=010a200101` is leftover last startup transmission and not confused with next command. `01011000` is standard HCI Read Local Version Information; existing `runtime_local_version_model.py` separate post-ATT profile has same command/response format.

Existing separate profile assumes ATT/remote completion, but those counters were 0 after this natural initialization. No fake connection/ATT event or counter change was injected to satisfy prerequisites.

## Selected profile

Only `component(completed_startup=True)` accepts version query when advertising initialization is complete, explicit runtime GPIO profile selected, startup commands/responses complete, runtime events/remote replies all 0, no pending, and GPIO settings valid. Default `component()` was byte-identical to existing unit-01 constructed component. Shared base C# was unchanged.

Response is existing virtual identity `0d34120d5a007856`, H4 `040e0c010110000d34120d5a007856`, not physical G2/EM9305 version information. Query cap is explicitly 1..32; sustained profile uses 32. Existing rules for opcode/byte/length/CS completion and rejecting writes during response remain. No general ACK of unsupported opcodes or always-ready behavior.

## Verification record and incomplete scope

Running new startup-only fixture with old post-ATT component failed at `version-header-supported`. This is red for expected functional difference; earlier unimplemented Python argument error is not counted as successful red.

Renode device tests passed normal 36, two-byte transmit chunks 44, maximum 32 queries 461, and default-disabled 3 checks. Maximum-version tests include short/long receive rejection and rejection after cap. They are not ARM firmware execution, and startup primer uses the same class's command getter, not an independent startup oracle.

`run_sustained_screen.py --controller-version-profile startup-mock` replaces only one pinned component and records profile, identity, cap, component SHA, and device-test SHA in plan. Saved audit checks reconstruction from original model/board using only permitted differences. Runtime inserts only original observation and does not alter original CPU branches, RAM, or tasks. Query transmission/response counts and runtime counters are read after stopping.

First integration test is private `sustained-controller-native-01/stock24`; execution source `source/tools` 790 files frozen in `sustained-controller-followup-bw496-01`. Until results, no claim of 60-second success, passing prior 8.16-second boundary, or full Goal completion. Prior repeated six-second evidence for three originals remains, with separate reverification needed under final integrated profile.

## Final observation of original run

That first integration ran to 31.144626 seconds post-screen/wall 457.57 seconds. It saved actual version commands 3/responses consumed 3, runtime/remote counters 0, no pending, Ready 0, RTC commit 1/RTC guard 0. First screen and six initial SRAM snapshots matched pinned baseline. Next original PC0x57f03c UART0 DMA start (offset 0x48/value 0x0a) stopped with guard 1. Full 60 seconds failed.

`peer` used in termination observation overwrote existing touch peer, causing original subsequent exporter to raise an EventFramesCompleted attribute error. This was observation-code error; failed capture execution_passed=false was preserved. Three version responses consumed, confirmed from source/binary evidence, are distinct from full capture success. New observation is function-isolated and rejects reassignment/global/nonlocal of original runtime names. Recurrence checks and 11 existing sustained checks passed. ARM/device components unchanged; next run observes guard details and UART/DMA state. Proof: private `sustained-controller-lifecycle-proof-01/report.json`.
