# E08 Completion Assessment for Pinned Storage Failure Scenarios

bw395. **The existing E08 acceptance wording in scope v3 was marked complete without changing it.** The total remains 16 conditions; fulfillment rises from 6/16 (37.5%) to 7/16 (43.75%, dashboard 43.8%). This percentage measures acceptance conditions, not estimated remaining work time.

> Assess damage scope and restart outcomes in pinned write/erase failure, interruption, and data/version mismatch scenarios. Do not cover failure with success; distinguish recoverable cases from explicit failure.

## Pinned verification set

| Scenario | Per-original execution scope | Confirmed result |
| --- | --- | --- |
| Runtime program completion withheld | Stock 2.4, 2.3, Faceclaw | No NOR write; previous record read by a new CPU. Upper-layer return 0 is not classified as storage success |
| Nonzero sector erase completion withheld | All three originals | Both NOR windows unchanged; strict stop on subsequent busy read. A new process's normal formatter matches the same original's normal SRAM/NOR baseline |
| Interrupted immediately before valid-state write | Stock 2.4 | Previous record selected despite payload being present |
| Interrupted after valid-state commit, before old-record cleanup | Stock 2.4 | New record selected due to one-byte state difference |
| CRC corruption outside FlashDB | Stock 2.4 | Corrupt record discarded and initial value rewritten as version 3. Not called recovery of the old value |
| Internal record CRC corruption | Stock 2.4 | Corrupt value loaded into RAM when outer CRC matches. Internal integrity rejection is unverified; not successful recovery |
| Valid CRC, future version 4 | All three originals | Expected version 3 confirmed by original instructions/logs, but version 4 also loaded into initial RAM. Do not extend this to a compatibility/safety judgment |

There are 13 rows when counted per profile. This does not mean every error combination ran on every original. The two interruption boundaries and CRC corruption are pinned to stock 2.4; program/erase failure and future version were compared across all three. Isolated ARM policy tests with synthetic peripheral ABI are distinguished from evidence of natural main execution.

## Damage scope and restart assessment

For withheld program/erase, no write was confirmed by before/after byte equality across both complete windows. Interruption tests checked KV range, preservation of NV neighbors and LittleFS, and the one-byte commit. Mismatch tests reconstructed declared corrupted bytes, CRCs, and hashes and checked the actual read result of a new CPU.

Mismatch restarts recorded the number of input-to-output changes, first/last offset, and full difference-list hash for KV/NV and LittleFS. All NV neighbors were preserved. LittleFS also receives writes during normal initialization, so it is not described as unchanged. Results were also compared with each original's normal restart output. Future version 4 LittleFS matched normal restart, while outer CRC corruption showed other changes too. Do not hide these differences or call them user-data recovery.

Only completed data was passed to a new Renode process; previous SRAM, pending timers, and controller state were not carried over. Stock original main, vectors, branches, returns, TCB, and SP were not forced. File/log/input lineage is pinned in independent captures and the research manifest.

## Preserved failures and limitations

**The 35-byte SRAM difference between observation on/off in Faceclaw erase failure remains unresolved.** Do not claim equivalent internal return sequences for the unobserved run. NOR, stop summary, and guards matched between runs; the new formatter's stored results were also compared separately. A 270-byte observation-related SRAM difference in stock 2.4 normal erase also remains. Distinguish audit passed from observer neutrality passed.

This completion is **classification** of failures, damage, and restarts for pinned scenarios. It does not mean the app handled errors correctly or recovered from every failure. The NOR error lost at the upper layer, unrejected internal CRC/future version, and subsequent unsupported GAF/CPDLP stops remain failures or unknowns.

Physical power removal, partial-bit erase/program, complete recovery of a valid user database, physical bootloader/stock recovery, and all storage addresses/versions/interruption points were not verified. The NOR model updates atomically at completion. Full app boot E05, runtime reset E06, natural display E09, and continuous updates E10 remain incomplete.

## Reproducible audit

`tools/verify_storage_failure_acceptance.py` rechecks file pins and meaning of existing evidence. It performs no new ARM execution or physical-device access. It recomputes original program/erase/interruption/mismatch audits, validates the source schema, and rejects missing or duplicate scenarios and false claims of complete app recovery. The final frozen-source report is byte-exact. Historical E08-incomplete flags in individual old reports are retained as records of their then-partial work.

```sh
<private-python> tools/verify_storage_failure_acceptance.py <simulator> <new-audit>
```

Evidence: private `storage-failure-acceptance-audit-02/report.json`, `storage-failure-acceptance-audit-frozen-01/report.json`, `storage-failure-acceptance-manifest.json` (authoritative for progress), and `storage-failure-acceptance-research-01/manifest.json` (identical research copy). Zero additional firmware executions; three coverage negative controls were rejected. This is not overall goal completion or physical installation permission. No Astra, other subagent, or external publication was used.

The next priority is the natural execution boundary of GAF/required services blocking E05/E09. Distinguish source-supported pieces from calculations without independent expected values; do not manufacture boot success with automatic ready, forced branches, or synthetic returns. The API screen checklist remains 3/6.
