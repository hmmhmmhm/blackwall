# Sufficiency and follow-up gaps in bootloader verification

bw-0552 · 2026-11-17. This reviews existing evidence; no new execution, implementation, or physical access occurred. Follow-up work is proposed and does not activate a new Goal.

## Current assessment

The current basis is sufficient for regression checking original bootloader→main→screen in one stock 2.4 combination. It is insufficient to judge recovery-patch installation safety, OTA interruption recovery, or full-stock restoration. Emulator-verifiable scope must be separated from dependencies on actual ROM, flash, power, and case.

## Already confirmed

- [Original boot final audit](original-boot-completion-audit.md): unchanged original boot/main bytes, natural handoff and same-board screen, two cold runs, and same-time guest SRAM/raw-frame comparison.
- [Rejection tests](original-boot-repeat-and-rejection.md): unknown OTA marker stops at emulator guard. Corrupt boot/truncated main are rejected by host SHA/size preflight. Neither establishes bootloader detection of damaged images or recovery success.
- [2.4 recovery patch candidate](bootloader-2-4-candidate.md): structure/rebuild and 118 limited tests of authentication, packet/CRC, streaming, recovery, and more passed. Serial is mocked; ROM writes/peripherals are substituted models. Test count is not converted to complete integrated recovery success.
- [Candidate handoff](combined-handoff-verification.md): 16 conditions with specified patch call location and R0, plus four corruption controls. This is separate from natural complete original stock 2.4 bootloader path success.
- [Storage failure](../research/storage-failure-acceptance.md): existing runtime NOR/KV scenarios. Do not carry this forward as verification of power-loss/partial-program recovery during boot MRAM update.

## Prioritized development proposals

| Order | Added verification | Completion criterion | Boundary |
| --- | --- | --- | --- |
| 1 | Boot-specific scenario runner/judgment | Trace original handling of normal, update pending, valid/corrupt metadata, invalid vector/range, etc.; distinguish vendor rejection, CPU fault, model unsupported, and timeout | Analyze actual format/check locations first; do not assume arbitrary CRC/signature rules |
| 2 | Natural integrated execution of recovery patch candidate | On one virtual board verify patched boot reset→actual UART2 receive/original initialization→authentication/recovery commands→handoff, comparing existing original baseline | Add integration evidence without replacing current specified-PC handoff and 118 host tests |
| 3 | Virtual MRAM update/failure lifetime | Judge write request→busy/success/failure→interruption→fresh reset→selection state and changed range; verify neighboring boot/metadata preservation and forbidden writes | Preserve current boot-readonly baseline and use separate explicit virtual profile. No unsupported success stub for ROM internals |
| 4 | Recovery/stock restoration repeats and version combinations | Check all modified-component hashes and reboot after restore for each supported combination, distinguishing patched-boot retention and full stock | Distinguish virtual host upload, UART2, and case relay. Not actual case/silicon safety certification |

For general modified-main CFW verification, extending per-candidate automatic scenarios for invalid GPU commands/pointers, IRQ/disconnect/timeout, frame readback, and storage regression is also valuable. The priority for this question is boot-specific failure/recovery integration. Full GPU/chipset precision reproduction is not required as a prerequisite.

## Remaining physical boundaries

Absent original Boot ROM, actual MRAM program/power-loss effects, silicon revision, charging-case USB/UART relay, each temple's recovery, and physical full-stock restoration cannot currently be certified. Virtual success alone does not authorize installation. Subsequent physical writes require user approval per operation.

The current Goal's 8/8 remains a completion history for normal original boot→screen scope, not reused as completion percentage for new recovery verification. This review generated no new builds, caches, or temporary execution artifacts.
