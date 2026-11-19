# Stock 2.3 and Faceclaw Timeout Recovery Profiles

bw412. **For both stock 2.3 and Faceclaw 38, the fixed scenario was verified from original main reset through long delayed disconnect, lost HCI response, actual timeout, controller reset/reinitialization, credit restoration, and original DM return for a new virtual connection.** Together with existing stock 2.4 evidence, fixed recovery scenarios exist for all three originals. The overall E14 determination is reserved for a separate integration audit.

## Per-original ABI

Stock-2.4-only addresses were not reused. Separate contracts check each pinned main hash, timeout callback bytes, timer/credit literals, and ready-function store and return. The shared peripheral model is byte-identical to the model verified for stock 2.4. Original main and guards were not patched.

| Original | Credit offset | Timeout return instruction | Normal-response observation point | Return instruction after credit restoration | New connection return |
| --- | --- | --- | --- | --- | --- |
| Stock 2.4, existing evidence | 22 | 563d24 | 563d32 | 563d3e | 4d3fc4 |
| Stock 2.3 | 1a | 546cd2 | 546ce0 | 546cea | 4cdb84 |
| Faceclaw 38 | 1a | 546cd2 | 546ce0 | 546cea | 4cdb84 |

Addresses and offsets in the table are hexadecimal. Matching callback bytes in the two older images do not establish identity of the full main images or all execution paths.

## Actual execution

Each original processed ATT/time and then handled a disconnect after 1000 ms of virtual time. Only one completion for re-advertising 2006 was lost; the original 10-second/1000 WSF-tick timer and actual WSF callback were observed. The host did not call the timeout directly or write credit, PC, or registers.

For both originals, six calls to the original timeout callback and the original WSF task and Thread/stack were confirmed. Original reset started subsequent generation 1 and processed 59 startup commands and 60 responses, including the advertising order where data arrives first. The original ready function stored credit from 0 to 1.

After cleanup, state/active = 0 was confirmed for three CCB slots, then a new LE event was injected. On the original ISR/SPI/HCI/DM path, opened was called once and reached 4cdb84. One CCB was reassigned with state 3/active 1, handle 40, and peripheral role. Decoded event, original task/kernel stack, IRQ/edge/counters, and absence of additional RTC writes were verified. Guard failures, CPU faults, and memory-policy violations were zero at every stage.

The sensor remained in the explicit frozen-core fault/pending state with zero calculations. This does not establish normal GAF, full app recovery, ATT on the new connection, physical firmware restoration, or radio behavior.

## Detailed observation controls

For each original, detailed recording hooks and a control retaining only three breakpoints were executed in separate native runs. Breakpoints were timeout return, normal response, and credit return. Report values, R0–R15, and all SRAM matched exactly at those three fixed boundaries. The control does not collect timer-entry/message/callsite/sender detail and is not represented as a separate success oracle.

Afterward, host polling stopped the cleanup interval at different times. The difference was not hidden or judged as overall equivalence.

| Original | Cleanup SRAM difference | Reconnection SRAM difference | Reconnection control time difference |
| --- | ---: | ---: | ---: |
| Stock 2.3 | 185 bytes | 354 bytes | -206.4 µs |
| Faceclaw 38 | 198 bytes | 463 bytes | -124.8 µs |

The complete 144 bytes of CCB, reconnection result, credit, IRQ, and task/stack matched between the two runs. The cause of every differing byte was not decomposed, so full hook-off equivalence and absence of effects from all observers remain unverified. Raw data and difference counts were retained.

## Audit and records

Twenty-eight checks per original, byte identity of the pinned tool's report, and both control comparisons passed. Six total mutations—credit not restored, wrong task, and live CCB before input for each original—were rejected even when SRAM/JSON/log/hash were changed consistently. Fourteen progress-management checks also passed.

The first audit incorrectly compared a structure aliased to diagnostics because the final-stage dict was expanded after saving. Only the audit was corrected to compare original phase files/logs and the expanded reconnection object separately. The input generator was then updated to preserve copies of phase dicts; the two native inputs and frozen generator used here were left unchanged. This record-format error was not hidden by the success of original execution.

Tools: `probe_peer_recovery.py`, `renode-peer-recovery-observer.cs`, `verify_peer_recovery.py`, `probe_peer_recovery_control.py`. Private evidence: `peer-recovery-version-native-01`, `peer-recovery-version-control-01`, `peer-recovery-version-research-01`. No physical device, Astra/subagent, or external publication occurred.
