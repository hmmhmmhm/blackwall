# E14 Communication Failure and Recovery Acceptance Audit

bw413. **The original scope-v3 E14 acceptance criterion was satisfied. Overall progress is 8/16 = 50.0%.** The denominator, acceptance wording, and support goals were not changed. This is not a unit-test count; it follows reverification of the nine pinned scenarios below using original ARM execution evidence. The audit itself ran no additional firmware.

Original criterion:

> Inject virtual peer disconnects, delays, and malformed messages, and confirm original timeout/error/state and reconnection or explicit failure. Unconditional ready/ack responses are prohibited.

## Pinned verification scope

| Scenario | Stock 2.4 | Stock 2.3 | Faceclaw 38 |
| --- | --- | --- | --- |
| Immediate disconnect | Original close, CCB release, app 28 notification | Same contract confirmed | Same contract confirmed |
| Malformed TPL CRC | Original ingress 1, app consumption 0, state/RTC retained | Same contract confirmed | Same contract confirmed |
| 1000 ms delayed disconnect + lost completion | Actual WSF timeout, reset/59 commands and 60 replies, credit restored, new DM connection | Same contract confirmed | Same contract confirmed |

The third row is a combined virtual scenario with an explicit frozen-sensor fault and lost BLE completion. The actual timeout occurs in the original timer/callback and is not confused with controller-reported disconnect reason 08. The original WSF task, Thread/stack, IRQ, and new CCB reassignment were checked. Virtual events enter the original handling path without a synthetic API caller or later PC/TCB/SP seeds.

For the first two rows, existing captures were reaudited with their pinned inspectors. Raw main, inputs, reports, memory, and semantic checks were compared; rather than trusting the CRC label, the actual input's last CRC byte was verified to differ by XOR 1 from normal data. Malformed paths in all three originals had no app consumption, application, or return and no extra RTC writes. Timeout recovery was checked using per-original ABI and the new recovery audit.

## Strict response policy

The shared model and 4,725 source pins in the parent manifest were verified. Actual original buffers, opcodes, lengths, split transfers, command order, corresponding replies, and maximum 59 are preserved. Only subsequent reset-generation advertising order 0/2/3/1/4 is explicitly allowed. Other order or bytes, short pulses, incomplete state, and exceeding the limit are not covered over with success responses.

Each actual Renode unit for active/default ordering has 2,863 assertions, including rejection of wrong payload bytes, extra startup, and insufficient generation settings. The existing native guard for 2008 versus 2006 mismatch and subsequent consumption of 59/60 in the exact order are also preserved. Unit tests are not described as original-main execution.

## Limitations and adjacent incomplete criteria

E14 completion is an assessment of this pinned communication failure/recovery set. It does not guarantee all BLE errors, physical timing, or physical-device recovery. ATT/TPL and complete app functionality on the new connection, and normal GAF, remain unverified; historical partial/unverified flags in those materials were not retroactively changed.

Detailed-hook controls matched complete SRAM and reports exactly at three pinned return boundaries for stock 2.3/Faceclaw. Later polling end-time differences and final 354/463-byte SRAM differences were retained. Equivalence of the full path with every observer hook removed is not claimed. CCB, credit, IRQ, original task/stack, and reconnection results matched in the controls. See [per-version recovery](peer-recovery-version-profiles.md).

Do not mark E05 normal services or E09 natural integrated display complete based on this result. The first-screen/API checklist remains 3/6. The eight remaining criteria are E05/E06/E09/E10/E11/E12/E15/E16.

## Reproduction and assessment

`verify_peer_failure_acceptance.py` checks scope version 3, 16 criteria, and original E14 wording, and requires exactly nine disconnect/CRC/delayed-timeout-reconnection × three-original combinations. Six existing native captures were reaudited with their then-frozen inspectors; three recovery captures were reaudited with dedicated semantic checks. Completion was not determined from a single metadata passed field.

The current audit and pinned tool report are byte-identical. Three coverage counterexamples—omitting Faceclaw recovery, replacing a scenario with reset-only, and adding an unverified row—were rejected. Nine existing semantic mutations and strict byte-level rejection evidence are pinned in the parent evidence. Fourteen progress-management checks also passed. The first coverage helper did not run under system Python because Capstone was missing; this is retained as an environment diagnostic. The actual audit and helper ran in the existing private venv.

The assessment manifest is `peer-failure-acceptance-manifest.json` at the simulator root outside Git. The progress manager checks hashes and sizes of the manifest and all child files. The audit required no additional ARM execution, physical-device access, Astra/subagent, or external publication.
