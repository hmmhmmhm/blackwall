# Collecting Paused SRAM After Observation

bw-0299. Only the runner was changed, without physical-device access. The default `guest-stop` policy is byte-for-byte identical to the existing exporter; original main, board, and peripheral models were not modified.

## Execution contract

Schema 2's `memory_export_policy: paused-after-observation` requires an explicit `host_capture_seconds` between 10 and 300 and a nonempty SRAM/ITCM export list. It cannot be used with `until-guest-stop`. After the observation deadline, memory is read only after the existing runtime's `PauseAll`. Guest branches and registers are not forced to change.

Pause state, PC, and executed instruction count are recorded before and after collection and checked for equality. These records must also match the final CPU report. Actual guest stops and expiration of the host observation deadline are recorded separately; strict MMIO, memory, and system-control error checks remain enabled. The same policy applies to file-length/SHA-256 and saved-log audits.

## Results confirmed

- Thirty-two runner tests passed, as did the same 32 tests on frozen source. Direct execution of the generated exporter confirmed that reads are blocked while not paused and CPU changes during collection are rejected.
- Stock 2.4 original main: after a 10-second observation, all 3,670,016 bytes of SRAM were collected. PC `0x40` and instruction count 18,679,453 matched before and after collection. File hash, logs, and stop-reason audit passed.
- Default-policy control with the same input: CPU, instruction count, events, and strict MMIO stop point all matched the existing results. The generated exporter string also matched the implementation before the change.
- Two native executions and three saved audits passed. The initial plan's missing case set was rejected before native startup, and its log was retained. Native runs of this policy were not performed for stock 2.3 or CFW.

Pinned evidence: `private:simulator/paused-snapshot-verification-01/manifest.json`. Original SRAM, firmware, and execution logs were kept outside Git. The observation deadline is host time and does not guarantee reproducible CPU progress. Do not interpret this `0x40` observation as app idle, normal boot, or successful display. Overall completion criteria remain 13/29 = 44.8%, scope v2 unchanged.

## Next work

Connect the five verified transactions in the [advertising initialization contract](../hardware/communication/address-advertising-contract.md) to an opt-in strict peer. Keep the default-off control and continue observing natural stock and CFW M55 execution. Use this SRAM contract when the deadline expires, but judge app-loop and screen entry from separate evidence. This does not authorize physical-device connection, installation, or writes.
