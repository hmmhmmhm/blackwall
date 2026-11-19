# Virtual full-stock restoration through original main

2026-11-17 · bw-0571. **Original main callback restored the full 159744-byte boot footprint; 39 original OTA verifier calls, full 4 MiB match, and fresh stock boot reset→main→576×288 display were confirmed.** BV11's virtual full-stock condition is complete, 8/12=66.7%. This is not physical installation/recovery certification, natural BLE OTA, or original Boot ROM execution.

## Execution path distinct from previous failure

The [existing resident boot writer](boot-self-restore-results.md) overwrote receive code in the extension and could not return normally. This task reused the [already verified original main callback](stock-main-ota-callback-results.md) unchanged. Original main is outside the boot footprint and does not depend on that receive code. Execution guard did not permit boot instruction fetch; violations were 0. The prior failure remains as a separate path, not overwritten as a successful fix.

A synthetic SRAM caller invoked original `5c69f8` in 4096-byte steps from 410000 through 436000, then original `446ab4` OTA verifier after each. Iteration/interruption control belongs to the diagnostic caller; writing, reading, comparison, capacity/IRQ/power handling are original main. This is not an OTA installer starting from natural boot/RTOS. Only ROM program 0200ff20 is an explicit functional model; initialized FPU/ITCM six bytes, HP22, and CCR reset 0 match the prior diagnostic profile.

Default 4 KB permission remains. Only ROM model in explicit `--boot-restore` profile accepts the 39 consecutive requests below. Incorrect range/order, source, length, key/op, or IRQ is rejected before writing.

| Item | Actual confirmation |
| --- | --- |
| MRAM destination | 410000..437000, 39×4096=159744 bytes |
| Source | Starts 20240000, increments 4096 per page |
| ROM requests | key 12344321 / op 1 / 1024 words / PRIMASK 1, exactly 39 consecutive |
| Original write/verifier | Callback/adapter/ROM/read callback/memcmp 39 each |
| Original bounds getter | 78 calls; device-info calculates and caches 4 MiB initially |
| Power/existing callback | Enable 39 / disable 39 / nonzero callback 78 |
| Per-page return | Callback 0 / verifier 0 / PRIMASK 0 confirmed on all 39 rows |
| Actual readback | Original read buffer collected at each verifier return, matching all 159744 payload bytes |
| End | 39 pages completed, SP 2007f000 returned, fault/guard 0, IRQ restored |

## Virtual original and restoration scope

Initial MRAM was the previous actual ARM main restoration result SHA 3e5f340e…, containing stock main 3700068 bytes, patched boot, and clear marker FFFFFFFF. Target was previously retained **synthetic virtual pre-modification 4 MiB**, with 9971 bytes after stock boot body 149773 defined as 0. Tail 0 is neither a physical backup nor a guess at bytes outside the official bundle.

Final native full MRAM SHA exactly matched the target virtual original:

```text
8e0e4761fa99f1c90f8080dc91c998d4379396cb059c2a929681c95083def7f5
```

Hashes and ranges of all changed persistent components—boot body, boot tail, and main—were supplied to the existing restore classifier, confirming full_stock_bytes=true. Full 4 MiB comparison separately passed, and outside boot footprint matched initial input. Main restoration provenance continues from actual output and pinned SHA of [previous full main ARM restoration](full-main-restore-results.md); main was not host-copied again here.

## Connecting actual results to a fresh boot

Actual writer output 4 MiB was supplied to `run_restored_boot.py --mode restored --boot-state stock-prefix --screen`. On a separate machine it progressed original boot reset→original handoff→stock main→virtual input→original UI/render. A normal 165888-byte, 576×288 frame with SHA 81200ab1… was confirmed. Original boot/main guest bytes, actual guest buffer, pre/post-pause SRAM/CPU, original stack lineage, and wire/observation records were also compared.

This fresh boot is a different machine from the function test, not same-board UART authentication/recovery completion. Existing reference GPU and virtual sensor/peer models are used. It does not prove physical ROM-program permissions, actual power loss, Boot ROM cold boot, left/right temples/case, or official-app OTA compatibility. Unsupported RTC logging after original verifier errors remains separate.

## Audit and cleanup

Writer, cold-boot, default-regression, and default-error-regression are retained outside Git in `simulator/main-driven-boot-restore-bw571-01`. Default 4 KB normal/ROM-error were rerun on current model to confirm functionality and default permissions remain. ROM error changes 0 bytes, callback 0, original memcmp mismatch, consistent with previous error-swallowing conclusion.

`main-driven-boot-audit-bw571-01` independently checked 39 integration conditions and 47 regression conditions. Post-cleanup `-02` reran saved audit-source and four support modules outside repo in `/tmp`, passing 40+49=89 conditions. It does not re-import current runner/model to judge historical runs. This result supports BV11 completion; test count itself is not added to progress.

Five input/permission-selection units and seven fresh-boot input/lineage units also passed. Four owned natives terminated and container absence confirmed; duplicate 4 MiB dumps/ELFs and reproducible cold-boot dumps totaling 28,067,197 bytes were cleaned up. Pre-removal actual full-MRAM hashes and removal receipts remain; after cleanup reconstruction uses the retained identical virtual original and SHA. Original inputs, source/assembly/caller binary, manifest, native logs, 39 requests/returns, actual readback stream, unique frame/SRAM, and audits remain. Firmware/private keys are not committed to Git.

## Reproduction

Existing pinned private inputs, Renode image, and LLVM 21 are required. Use a new output name.

```sh
bw_assets="$HOME/Library/Application Support/Blackwall"
python3 -B tools/run_stock_main_mram_probe.py "$bw_assets/simulator/boot-restore-new-01/writer" --entry callback --fault success --chip-profile --delay-profile --verification ota --boot-restore
python3 -B tools/run_restored_boot.py "$bw_assets/simulator/boot-restore-new-01/writer" "$bw_assets/simulator/boot-restore-new-01/cold-boot" --mode restored --boot-state stock-prefix --screen
```

Repo-independent audit of this frozen evidence:

```sh
python3 -B "$bw_assets/simulator/main-driven-boot-audit-bw571-02/audit-source.py" "$bw_assets/simulator/main-driven-boot-restore-bw571-01" "$bw_assets/simulator/boot-restore-audit-new-01"
```

Remaining [12 conditions](../data/bootloader-validation-progress.json) are BV02 original pending ROM path, BV05/06 same-board authentication/recovery, and BV12 version combinations. Full-stock success in this specific virtual 2.4 profile does not establish safety of other combinations.
