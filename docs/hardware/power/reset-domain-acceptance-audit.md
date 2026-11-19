# Reset Domains and Acceptance Audit

bw-0420. Following the previous memory-read protection fix, retention/initialization policies were compared against actually compiled models and original reset material. **A second defect—virtual cache state remaining after reset—was found and fixed.** Successful scope of original-main restart is distinguished from E05's incomplete initialization.

## Cache-state defect found

The three bw419 original captures had `system_control.icache=true` even at reset entry. `BlackwallSystemControl` is a manually attached helper that continued overlaying IC/DC enabled values on CCR reads after CPU reset. D-cache selector and 2048-line initialization history also remained, allowing cache enable without initialization on a new boot. This is functional state that cannot be fixed by merely labeling the helper an observer.

Existing system-control SHA256 is `82067ed1bdc22110330293a607718714e92b074d6835bee55cd761ae9e58d53c`; corrected SHA256 is `5564e88984c662868830211cc1c2362fc15460159f1f4f54a967ef44623938f5`. Immediately after CPU PeripheralReset, IC/DC enabled, selector, initialization bitmap, and per-boot cache counters are initialized. Violation counts/last-error diagnostics remain cumulative. Existing hooks/register definitions are not installed twice.

The synthetic M55 guest in `probe_reset_cache_lifecycle.py` performs IC invalidate, full DC set/way initialization, and both cache enables on first boot, then resets via external AIRCR or guest AIRCR. Second boot has four cases: CCR read, missing IC initialization, missing DC initialization, and normal reinitialization. All eight baseline cases failed and all eight corrected cases passed. Read results, actual subsequent markers, and policy violations are checked together, so changing only host fields cannot pass. Synthetic guests are separate from original G2 main execution.

## Declared virtual reset domains

| Domain | Policy | Evidence and limits |
| --- | --- | --- |
| CPU/NVIC | Original reset vector/SP; initialize masks/IRQ state | Three original entries, BASEPRI and existing synthetic IRQ controls; not full M55 ISA/security certification |
| Main image | Preserve pinned input; prohibit guest writes | Original hashes and memory protection tests; bootloader not executed |
| SRAM | Preserve backing, then original startup rewrites globals/stack | Pinned MappedMemory.Reset no-op and synthetic cookie retention; changes between asynchronous request and entry are not interpreted as pure reset loss |
| ITCM | Preserve backing and guest-written provenance | Original full-region hash/written byte count, synthetic code re-execution without rewriting |
| NOR KV | Preserve backing, initialize PIO transfer state | Full selected KV-window hash and idle state; in-progress program/erase interruption not tested here |
| LittleFS window | Preserve backing | Compiled no-op Reset and additional-window connection; only source-supported because full window hash not collected |
| RTC | Initialize virtual 2000 epoch, write latch, commit | Original reset entry and new ATT commit; not generalized to actual G2 RTC reset behavior |
| Virtual controller peer | Initialize session, queue/history, consumption counts | Entry Unreleased/0/0, 59 service-restart commands, new connection/app events; not controller firmware execution |
| Functional cache | Initialize IC/DC enabled, selector, initialization history | Eight synthetic cases and original true→false→true; not physical dirty-cache/timing model |
| Other peripherals | Registered Reset and owner-helper Reset | Compiled source; not every non-idle state independently verified |
| Observation/safety helpers | Preserve pinned hooks/protection provenance; release owned one-shot observations only | Input and adversarial-code controls; observer neutrality and full sleep history after overflow unverified |

[MappedMemory.Reset](https://github.com/renode/renode-infrastructure/blob/cd4b002aac2398994c4a61a34a8b31b5700facf2/src/Emulator/Main/Peripherals/Memory/MappedMemory.cs) in pinned infrastructure `cd4b002aac2398994c4a61a34a8b31b5700facf2` does nothing to memory contents. This model policy is not a physical SRAM-retention guarantee. Actually executed compiled source and the upstream file are pinned in the private manifest.

## E06 assessment and next dependency

Device-boundary reset, original vector re-entry, verifiable portions of declared domains, and reprocessing by service/ATT app were demonstrated. However, E06 wording requires restart **during E05 execution**. E05 required initialization and full app lifecycle remain partially complete. A scenario pausing at the current getter observation boundary and then injecting a virtual phone is not interpreted as normal initialization completion.

Thus E06 remains partial, overall 8/16=50.0%, display checklist 3/6. Acceptance wording and denominator are unchanged. Instead of adding more variants of the same reset/control inputs, return to E05 GAF calculation, subsequent consumption, and legitimate initialization path. Without calculation specification/code, exact ROM execution contract, or independent input/output expectations, do not create ready or derived RAM to force success. Existing WHOAMI/NAK failures also have not proved upper initialization return and are not treated as a bypass success path.

## Reproduction and preservation

`--system-control <pinned-source>` was added to `probe_reset_restart_versions.py` and audit. Along with bw419's `--memory-policy` candidate, only two pinned compiled source portions are replaced. Default recipe and prior audits remain.

```sh
<private-python> tools/probe_reset_cache_lifecycle.py <simulator-root> <new-output>
<private-python> tools/probe_reset_restart_versions.py <simulator-root> <new-output> --case stock24 --memory-policy <pinned-policy.cs> --system-control <pinned-system-control.cs>
<private-python> tools/audit_reset_domains.py <simulator-root> <three-original-capture-root> <new-audit>
```

Proprietary originals, SRAM, and NOR are outside Git. Material is preserved privately in `reset-cache-lifecycle-native-01/02`, `reset-cache-original-native-01`, and `reset-domain-acceptance-research-01`. No physical-device access, writes, Astra/subagents, or external publication occurred.

All three originals passed IC enabled → reset-entry disabled → enabled after service reinitialization, plus new connection/ATT/one RTC commit. Thirty-two saved audits each and eight synthetic cases passed; five counterexamples with consistent logs/reports for cache-initialization bypass, stale cache at original entry, source omission/duplication, or incorrect baseline registration were rejected. Frozen regeneration of domain report and three original audits is byte-identical, checking 297 source/capture pins. Fourteen progress-management checks also passed. Earlier failed/successful material remains unchanged.

Original-specific ABI/reset paths follow [bw418](reset-restart-version-profiles.md), and read-protection lifecycle follows [bw419](reset-memory-protection-lifecycle.md). Reinitialization execution path and virtual time may differ with this source change; differences from earlier sleep times are not interpreted as physical performance differences.
