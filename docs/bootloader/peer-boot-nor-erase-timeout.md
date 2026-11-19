# NOR erase failure by original and fresh-process controls

bw394. Non-FF NOR erase failures were executed from actual ARM main reset for stock 2.3 and Faceclaw. Five existing stock 2.4 runs were reused. Ten new runs comprise normal observation off/on, failure off/on, and preserved-NOR fresh process for each original. No physical device or subagent was used.

## Saved results

The first 4096 bytes use a repeating 00..ff pattern with 4080 non-FF bytes. Existing `completeSectorErase:false` defers completion. For both originals, at erase started 1/completed 0 and program 0, complete KV/NV and LittleFS backing remained unchanged. Original branches, returns, TCB, and SP were not forced.

Observed return chain is poll 1 → NOR 4 → adapter 0 → partition 0 → FlashDB 0. Upper-level 0 does not mean actual storage success. On a subsequent read, busy read at PC `0x4db672`, opcode `0x6c`, target `0x1fc1000` hit `guard_iom7_tail`, with exit 1 retained.

Only completed backing was imported at CPU instruction 0 of a fresh process. Prior SRAM, timers, and controller state were not transferred. Restarted formatter with normal erase configuration matched normal observation-on full SRAM, both NOR windows, and initial return chain.

| Original | Normal and restarted erase/program | Initialization-wait PC | Normal on/off SRAM difference | Failure on/off SRAM difference |
| --- | --- | --- | ---: | ---: |
| Stock 2.4, existing evidence | 136/270 | `0x5542c6` | 270 bytes | 0 |
| Stock 2.3 | 136/268 | `0x52046e` | 0 | 0 |
| Faceclaw | 135/266 | `0x52046e` | 0 | 35 bytes |

## Failed observation contract

**Observer neutrality on Faceclaw's failure path was not established.** All 35 differing bytes and failed `fault_observer_ram_exact` contract were retained. Addresses were not excepted or results changed to exact. Although NOR, stop summary, and guard match with observation off/on, verification is not extended to the unobserved execution's internal return chain. The 270-byte difference in stock 2.4's normal path is also unresolved.

Final audit passed means input lineage and classification of these results are consistent. Faceclaw report retains `observer_fault_sram_exact:false`, `observer_neutrality_unproven:true`, and `unobserved_error_return_chain_verified:false`. Initial exact-contract and frozen-audit failures were separately recorded.

First stock 2.3 audit failed by assuming 2.4's 270 programs as a common value. It was corrected to per-original fixed counts confirmed in independent normal off/on and fresh-process runs; guest was not rerun.

## Verification and limitations

The 124-check three-family integrated audit, byte-exact frozen report, and byte-exact previous stock 2.4 report were confirmed. Three negatives consistently modifying JSON/log/hash to conceal an error return, fabricate erased bytes, or use the wrong restart image were rejected. Fourteen progress-management checks passed.

This covers failure, damage extent, and formatter response to a synthetic initial pattern. It does not verify recovery of existing user data, full app boot, physical partial erase, or actual power loss. The atomic-completion model's limitation of updating an entire sector at timer completion remains.

Pinned evidence: private `boot-nor-erase-peers-01/{stock23,cfw}`, `peer-boot-nor-erase-audit-02`, `peer-boot-nor-erase-audit-frozen-02`, `peer-boot-nor-erase-research-01/manifest.json`. Tool `verify_boot_nor_erase.py --all-originals` audits only saved runs and starts no new ARM execution.

Next combine pinned write/erase failure, interruption, and data/version mismatch evidence under existing E08 wording to decide completion. This task alone did not complete E08; overall is 6/16 (37.5%). Full app execution and reset in E05/E06 remain separate conditions.
