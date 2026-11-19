# Virtual Reset Delivery from a Watchdog Request

bw-0425. The default watchdog model retains its stop at the request boundary. Optional `watchdog_reset_delivery_model.py` delivers reset only when both an explicit main-only virtual boot contract and RSTGEN WDREN are enabled. It does not include physical-device or ROM/SBL execution.

## Independent ARM contract

The original model remained at boot count 1 even with gate 2, failing reset-delivery checks. The new model stops at the request boundary with gate 0/1 and re-enters the guest reset function through the actual M55 vector with gate 2/3. Rebooted guest reads WDT CFG 0, RSTGEN CFG 0, and selected virtual cause WDRSTAT `0x40`. No host PC/SP seed is used.

An additional lifecycle test performs two watchdog reboots followed by one normal machine reset. Guest boot count is 1→2→3→4, cumulative watchdog deliveries 2, and final normal-reset cause 0. This is a declared virtual boot contract, not the actual G2 warm-reset cause accumulation/retention policy. Twenty-eight gate-matrix and ten lifecycle checks passed.

`RequestReset()` in [pinned Renode Machine source](https://github.com/renode/renode-infrastructure/blob/cd4b002aac2398994c4a61a34a8b31b5700facf2/src/Emulator/Main/Core/Machine.cs) schedules machine reset in a synchronized state. It does not arbitrarily overwrite CPU registers or call Reset immediately inside the timer callback. The virtual cause is recorded before scheduling delivery and moved to next-boot state in controller Reset. Two default source files were unchanged; transformation applies only to exact SHAs.

## Original integration boundary

The original test uses stock 2.4 main, existing frozen GAF failure scenario, explicit virtual HCI identity, and shared IOM power model. Watchdog configuration and original 200,000-iteration timeout loop remain. Existing verified initial vector/NVIC, memory protection, and cache-reset lifecycle are used. The observer installed after ATT stops at the original reset vector.

The first original attempt was rejected during platform creation because separate STAT mapping overlapped an existing startup-guard range. It failed before ARM execution and is not success evidence. The corrected original test does not add STAT bus mapping; it collects the controller's virtual cause only as host diagnostics. Independent guest cause reading and **original G2 main cause consumption are separate**. Supporting original STAT consumption requires explicit dispatch only at the relevant existing guard address and verification of supported widths and write rejection.

Required initialization, return to app services, and lifecycle of all active peripherals after original reset require further verification. E05/E06 are not marked complete. No physical-device access, writes, subagents, or external publication occurred.

## Original execution result

In corrected `watchdog-reset-entry-native-02`, original ARM re-entered reset vector `0x5fbe3e`, SP `0x2007fb00`, VTOR 0x438000 after the watchdog request. Delivery and NVIC reset were one each, pending=false, WDT CFG 0, and virtual cause 0x40. Fault/CFSR/HFSR/memory violations were 0; initial, connection, and ATT SRAM snapshots were exact against the previous baseline. The observer stops before subsequent instructions execute, so this is not evidence of full app return.

Fifteen saved-material audits, 38 independent ARM contract checks, and three semantic counterexamples passed. Regenerated inputs and saved logs were compared. The older-schema unit report without a lifecycle array was checked as a single actual log result without rerunning ARM. Material and audit source are preserved privately in `watchdog-reset-delivery-research-01`. Overall progress is 8/16=50.0%.
