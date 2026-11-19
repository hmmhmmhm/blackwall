# MSPI0 Disabled Queue/IRQ Model and Natural Main Integration

bw-0308. Connected the [original contract](mspi0-queue-irq-retention-contract.md) to an optional model. Three original main inputs progressed on M55 through queue initialization, intermediate configuration, and IRQ configuration to the CQFLAGS read in the retention-power function. **Overall acceptance remained 13/29 = 44.8%, scope v2.** Full boot and integrated display were incomplete.

## Changes and limits

Added `mspi0Initialization` to `BlackwallMspi1ConfigStorage`, off by default. Selection requires an MSPI0 address, nonexecuting CQ configuration, and independent interrupt bank. Existing MSPI1 storage, set/clear, and IRQ operations are reused with separate instance state.

- CQCFG stores priority only and rejects execution bit 0. DMA/PIO start remains rejected.
- CQFLAGS and MSPI0 CQSTAT remain unknown. Queue/DMA/panel completion responses are not generated.
- MSPI0 IRQ bank connects to NVIC20. With no actual transfer event, natural-execution status is 0 and only clear/enable configuration occurs.
- Reads/writes require passing the existing power gate. XIP/NOR, PIO, and power off/restore models were not copied.
- Existing default MSPI0 configuration continues to block queue access. Eight sources including shared core/clock and six other models were unchanged. Only the config model file changed.

## Natural execution results

| Input | New stop PC | Stopped operation | Result |
| --- | --- | --- | --- |
| Stock 2.4.0.24 | `0x4e92dc` | 32-bit `CQFLAGS(0x400602b0)` read | Blocked as unknown |
| Stock 2.3 | `0x4dbf08` | Same | Same |
| Faceclaw 38 | `0x4dbf08` | Same | Same |

For all three, confirmed original `ldr.w r1,[r1,#0x2b0]` with R1=`0x40060000`. Execution advanced naturally from the prior queue-index write boundary without modifying PC, returns, branches, or firmware bytes. It uses the existing board profile starting at main reset. Do not extend this to full ROM/bootloader boot or physical verification.

Common observations:

| Observation | Value |
| --- | --- |
| Config reads/writes | 28 / 20 |
| CQ storage reads/writes | 5 / 6 |
| CQCFG / software flags | 2 / `0x80` |
| Successful CQFLAGS reads | 0 |
| IRQ-bank reads/writes | 3 / 2 |
| IRQ enable / status | `0x1a80` / 0 |
| Prior BLE commands/responses | 59 / 60 |

The intermediate configuration call left unexecuted in bw307 progressed through the existing model in natural main here. No skipping hook was added. This passed IRQ-bank setup, not an actual panel IRQ event or completed service.

One default-model control exactly matched prior CQCURIDX-blocked PC, instruction count, full observed state, and selected events. All three candidates preserved the previous event prefix.

## Verification and preserved failures

- Passed 33 new unit, 33 frozen-copy, 33 existing MSPI0 config, and 33 existing MSPI1 CQ checks. They reject start, unknown status, invalid index/address alignment, power-gate violations, and changes to other instances, and check independent IRQ set/clear/reset. Manual pending injection in unit tests is not a natural-main panel event.
- Completed three native candidate runs, one default control, and four saved re-audits. Initial candidates failed only semantic verdicts because bounded capture was expected; original reports were preserved. Added strict boundaries confirmed from original instructions to a separate audit contract without rerunning CPU.
- The first CFW re-audit was rejected because its plan included diagnostics from another input. An audit changing only semantics in the saved CFW plan passed. The runner was not weakened to permit mismatched execution configuration.
- The first new unit failed because the new option was absent. An existing MSPI1 CQ harness was rejected before execution under an outdated core-identity assumption. Kept existing driver/board and used an already-existing current-core assembly function for regression checks. Missing Unicorn in system Python was also recorded as a pre-execution failure and reproduced using the pinned venv.

Tools: `prepare_mspi0_queue_candidate.py`, `verify_mspi0_queue.py`, `inspect_mspi0_queue_profiles.py`. Native runner and model defaults remain.

Private evidence is pinned in `simulator/mspi0-queue-peer-verification-01/manifest.json`. Froze 83 Python dependencies and required C# inputs; saved-analysis report/inspector each match byte for byte. Native runs/audits remain in `mspi0-queue-main-01/`, `mspi0-queue-control-01/`, and `mspi0-queue-saved-audit-01/`.

## Next work

Verify bits used in restoration after the full CQFLAGS word is saved to shadow together with power off/on paths. Do not arbitrarily fill input/completion/idle bits. Once that contract is confirmed, connect MSPI0 power retention and proceed toward actual panel transfer/framebuffer paths. The web installation/recovery boot goals and per-operation approval boundaries for physical writes remain unchanged.
