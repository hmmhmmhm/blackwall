# Virtual Controller Version Query and Watchdog Pause

bw-0423. **Original stock 2.4 ARM sent HCI 0x1001 and read the entire explicit virtual version response.** Connecting the existing IOM shared-power lifetime model advanced beyond the earlier communication boundary and ran another 12.0050502 virtual seconds after ATT app handling. Guard, CFSR/HFSR, and memory violations were zero during this interval. GAF remained busy; normal calculation was unsupported.

## Limited virtual response contract

`runtime_local_version_model.py` is optionally composed only with pinned controller source `3f830d6c…`. The original source file and default board are unchanged. It accepts only exact H4 `01011000` after the declared ATT/remote-feature workflow finishes and GPIO117 configuration is valid. Query budget is 1..32; default is disabled.

Selected identity `0d34120d5a007856` is test input, not a version read from actual G2/EM9305; it is recorded as `physical_identity_verified=false`. The Command Complete format follows [Bluetooth HCI §7.4.1](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html). The H4 response containing success status and eight-byte identity is `040e0c010110000d34120d5a007856`.

| Field | Selected virtual input |
| --- | --- |
| HCI version | 0x0d |
| HCI subversion/revision | 0x1234 |
| LMP version | 0x0d |
| Company identifier | 0x005a |
| LMP subversion | 0x5678 |

Accepted request and consumed response counts are separate from startup's 59 commands/60 responses. Checks cover bytes, length, transmit fragments, CS completion, rejection of writes during a response, RDY/GPIO IRQ, exhausted budget, and reset. Other opcodes are not ACKed. Do not extend this to support for all initialization or version queries on other firmware/at arbitrary times.

## Device tests and actual original execution

The existing device-test model failed at `version-header-supported`. The final normal 63, two-byte fragment 71, default-disabled 26, and maximum-32-query 483 checks passed, totaling 643. These tests use SPI/GPIO transactions on an actual Renode device class; they do not execute ARM firmware. The startup primer uses the same class's command getter, so it is not an independent startup oracle.

A preliminary one-byte write-capacity test was rejected at startup command 44/header budget 944 before the version query. Both artifacts were retained; the supported two-byte fragment fixture was tested without increasing guard budgets. Normal operating-profile capacity 9 remains unchanged.

| Original execution | Result |
| --- | --- |
| native-01 | One version request accepted; existing power guard at IOM6 off request EA0 while waiting for response. Zero responses consumed |
| native-02 | Selected verified shared HCPB/HCPC model. One request/response, GPIO IRQ cleanup, peer Complete. Virtual 12.005 seconds, busy 13,686, zero guards/faults |
| timeout-native-01 | Same profile run longer. Unclassified pause at virtual 13.2466635 seconds and busy 15,132. GAF timeout not reached |
| pause-native-01 | Collected actual call stack for state change. Confirmed Apollo510 watchdog reset-request timer callback called `PauseAndRequestEmulationPause` |

At watchdog pause, `InternalPause=false` and machine aborted=false. This evidence rules out the hypothesis that an internal pause was mistaken for the cause. Four full SRAM snapshots—initial, connection, ATT, and final—and existing result JSON values matched exactly before/after adding the observer. This is not general observer noninterference or physical timing validation. CPU PC `0x496624` at the stop is where execution happened to be during the asynchronous watchdog event, not the causative instruction.

## Completed scope and next step

This pinned virtual version-query contract was verified. **Original GAF 200,000-poll timeout return, normal calculation, and complete initialization remain unverified; actual virtual reset due to watchdog has not yet been executed either.** Do not disable the watchdog or change original loop count, branches, TCB, or SP. Next check actual watchdog settings, reset gate, restart requirements, and their relationship to CPU execution/delay clock profiles. Do not ignore and resume past the existing intentional watchdog stop.

`verify_runtime_local_version_capture.py` compares the compiled model, regenerated input bytes and manifest JSON values, saved logs, original hash, prior SRAM prefix, and full results. It rejected three counterexamples: lost response consumption, forged physical identity, and forged watchdog-pause classification. Fourteen progress-management checks also passed. All 16 conditions and statuses remain unchanged: **8/16 = 50.0%**, screen checklist 3/6.

## Resource recovery and evidence preservation

After the pause result was saved, the Docker socket disappeared and automatic container-termination confirmation failed. OrbStack was Stopped and free space was 243 MiB. A partial SRAM block-sharing attempt stopped with ENOSPC, but original SHA values of all 174 processed files remained unchanged. Then 613 identical SRAM files were shared as independent APFS COW copies, securing about 1.5 GiB free at that time. Paths and bytes were preserved; hard links and original deletion were not used.

After OrbStack/Docker recovery, no container was found mounting the pause capture. Do not count this resource failure as a firmware fault or GAF timeout. Material is private in `runtime-local-version-{unit-*,native-*,timeout-native-01,pause-native-01,research-01,resource-recovery-01}`. Proprietary main/SRAM/NOR stay outside Git; no physical-device access, writes, Astra/subagent, or external publication occurred.
