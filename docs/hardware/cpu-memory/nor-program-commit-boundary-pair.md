# Original Restart Comparison Before and After NOR State Commit

bw387. Compared before and after the new KV record's state update in original stock 2.4. **Even with identical stored payload, whether one state byte had completed caused new main to select the previous stored value or new input differently.** E08 remained incomplete; overall 6/16 = 37.5% and API display 3/6 were unchanged.

## Causal control

| Boundary | Program starts/completions | Completed bytes | New state `0x1fc0245` | Previous state `0x1fc0082` | RAM record in new main |
| --- | --- | ---: | --- | --- | --- |
| Sixth program WIP | 6/5 | 40 | 7f | 1f | Previous `010000002b2d37682000f018` |
| Seventh program WIP | 7/6 | 41 | 3f | 1f | New `0300000000f153651000fe58` |
| Normal completed control | 7/7 | 42 | 3f | 0f | New value confirmed in bw384 normal restart |

The first two NOR images differ only in one byte, `0x1fc0245` 7f → 3f, a 1 → 0 transition completed by original programming. The 12-byte payload, CRC, prior record state, and neighboring NVdb/LittleFS are identical. Completing the seventh pending program changes previous state 1f → 0f, but the new value is selected even before that cleanup. This is an observation for this storage scenario, not a general guarantee for all FlashDB states, objects, or migration.

“Previous stored value” means the value present before this ATT input, not necessarily an earlier time. The new input is timestamp 1700000000, zone 16.

## Original execution and reuse

Reused bw386 control, sixth interruption, and first restart after hash verification. Only two new native executions occurred: one seventh interruption and one new main reset. Used the same observer, model, board, original main, and initial SRAM/ITCM. All seven rows of the new interruption exactly matched the control's seven rows, including PC, SP, and WIP results. Potential observation-hook effects were checked only within the prior pinned control's report and full SRAM/NOR comparisons.

Both restarts loaded only two completed NOR windows at CPU instruction 0. Previous guest SRAM and pending timer/program state were not imported. Original main instructions, branches, returns, tasks, stack, and IRQ were not forced. This test omits incomplete operations from the new process under the existing atomic-completion model; it does not reproduce physical power loss or partial-bit program/erase.

After reading the new record, new main still stopped at the unsupported CPDLPSTATE 22 write at PC `0x4956e2`. Restart CLI exit 1 and full boot false were preserved. The earlier boundary also stopped at the same unsupported PC. Do not describe data-selection confirmation as whole-app recovery or completed boot.

## Integrated audit

Extended existing `verify_nor_program_cut.py` to support `--phase before-old-retire` and `--phase both` rather than adding a nearly identical checker. The new default sixth-boundary audit report was byte-exact with the prior frozen report, leaving its judgment unchanged.

The pair audit checks 25 items per boundary and four relationships between them, including unchanged model/main/inputs; WIP/completion/byte counts; original-observation row prefix; exact NOR difference; neighbor preservation; new-process inputs; actual RAM/log/report; and original unsupported stop. The pinned-source pair report is byte-exact. Three semantic negatives consistently altering JSON/log/SRAM/hash—canceling state commit, false completion, and selecting the old value after commit—were rejected by actual state/counter/selection checks respectively. Fourteen progress-management checks passed; zero Docker containers remained after execution.

```sh
<private-python> tools/probe_nor_program_cut.py <simulator> <normal-writer> <new-cut> --stop-program 7
<private-python> tools/probe_runtime_kv_restart.py <simulator> <cut-capture> <new-restart> --retained
<private-python> tools/verify_nor_program_cut.py <simulator> <new-audit> --phase both
```

Pinned captures are private simulator `nor-program-cut-native-01/before-old-retire` and `nor-program-retire-restart-01/stock24`. The preceding sixth boundary and control use existing paths unchanged. Audit: `nor-program-pair-audit-01`; frozen: `nor-program-pair-audit-frozen-01`; full pins: `nor-program-pair-research-01/manifest.json`. Dataless packages were run using the previously documented local dependency wrapper.

## Next completion criteria

This program-commit selection boundary for stock 2.4 was closed. Do not keep expanding the same state/time variations. The next required dependency is actual write/erase failure and original busy-timeout/FAL error propagation. Existing stuck records stopped strictly on the next read from a busy device after timeout and therefore do not count as safe recovery. Connect error returns, upper original branches, remaining backing, and new-reset results. Stock 2.3/Faceclaw cross-verification and stored-version mismatch also remain.

E08 and E05/E06 remain incomplete; 16-condition acceptance/status/evidence and API 3/6 are unchanged. There was no physical access, flash, OTA, Astra/subagent, or external publication.
