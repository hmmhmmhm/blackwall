# Full RAM and RTOS Context from Original Main

Follow-up bw266 connected [M55 original PendSV save/restore and caller resumption](../hardware/display-gpu/nema-native-pendsv-resume.md) in a limited PSP test. It is not full machine checkpoint restoration or original-main resumption.

Work `bw-0265` follows the PendSV boundary in [GPU IRQ connection](../hardware/display-gpu/nema-native-irq-completion.md). Full mapped RAM from original main was collected to obtain scheduler state and other task stacks beyond partial SRAM. It is not described as a complete machine checkpoint or successful resumption.

## Read-only export

Optional `post_stop_memory_exports` was added to schema 2 plans in `tools/run_native_candidate.py`. Existing plans are unaffected.

- Only mapped ITCM `0x00000000..0x00040000` and SRAM `0x20000000..0x20380000` are allowed. MMIO and firmware ROM are rejected.
- At most four `.bin` files with unique lowercase kebab-case names are allowed. Path escapes and invalid sizes/formats/ranges are rejected.
- After both existing guest stop and machine pause are confirmed, read using `ReadBytes(..., onlyMemory=true)`. Guest memory, registers, and PC are not written.
- Docker input mount remains read-only; only a new `exports/` directory is separately writable.
- Native records SHA256; host independently checks length/hash. `--audit-existing` also rechecks exports and stores hashes.

Execution plan is `tools/original-main-full-memory-candidate.json`. Alongside existing RTOS diagnostics, it exports **SRAM 3,670,016 bytes (3.5 MiB) and ITCM 262,144 bytes (256 KiB)** separately. Each image's own snapshot is preserved.

## Agreement with original execution

Stock 2.4, stock 2.3, and Faceclaw 38 all ran from existing reset and stopped at the same unsupported SPI DCXCTRL boundary. Full CPU observations, instruction counts, and existing events exactly matched each no-observer baseline, and schema 2 semantic checks passed. No new PC hook was added.

TCB, current SP, OtherSP, and saved-SP regions in full RAM matched separate diagnostic words. Kernel globals and existing SRAM observation windows also matched. Initial A5 fill and zeroes are retained but not interpreted as actual initialized device state. These are model results of original execution, not physical dumps.

First collection failed before export because SHA256 type could not be loaded. Separate runtime API inquiry established that `clr.AddReference('System.Security.Cryptography')` was required; it was corrected. The failure directory was preserved.

## Task structures and original selector checks

`tools/inspect_original_rtos_memory.py` finds TCB candidates in full SRAM whose self-owner fields, priority, and stack ranges agree, then cross-checks:

1. State-list sentinel, length, index, and actual node count.
2. Each node's bidirectional links, owner, container, and TCB agreement.
3. First PSPLIM word of saved frames for non-running tasks against stack base, and EXC_RETURN format.
4. Current TCB against kernel globals found in source.

For each image **30 TCB candidates and 29 saved headers for non-running tasks** passed checks. Actual names including `displaydrv_mgr_task`, `ui_task`, `ambiqdraw`, `input`, and BLE tasks were read. These are structure-candidate/link checks, not a claim that all FreeRTOS fields or total task count were fully identified. Candidate stack-depth words remain distinct from uninterpreted fields.

Current `ble_wsf` TCB's saved SP points to a location already overwritten by the running stack. Unlike non-running tasks, its saved header must not be restored as current CPU context. Current PSP and full public CPU/FPU register values must be handled separately.

A separate **Unicorn Cortex-M7 function fixture** executed the task selector called by original PendSV itself. Original ROM and full SRAM were supplied; it returned through original `pop ... pc` without observation hooks, fake services, or forced successful return. All three images reselected current `ble_wsf` at priority 49. Only three words of task-trace records found in source changed in SRAM. This is **not execution of full PendSV/exception return on M55**.

Stock 2.4/2.3 had eight state-list containers for candidate tasks; Faceclaw had seven. Stock 2.3 `audio` was in a separate container, while Faceclaw `audio` shared one with 23 other tasks. Exact cause is unknown and is not immediately classified as patch defect or specific wait state. It demonstrates that each image's RAM must not be mixed even with identical kernel code and TCB addresses.

## Verification and material

- Four new export-boundary tests were confirmed failing before implementation. Final **17 unit tests passed** including existing semantic contracts.
- Of four original-main native runs, three final collections and three schema 2 semantic checks passed; the remaining run failed export import. One separate API query did not start a guest.
- `--audit-existing` passed for three new collections and one older collection without exports, without native reruns.
- Full RAM checks and original selector function execution passed for three images. Final results with strengthened provenance checks were adopted.

Material outside Git under `simulator/`:

| Path | Content |
| --- | --- |
| `original-main-full-memory-01/stock24` | SHA256 import-failure input/log |
| `memory-export-hash-api-01` | Runtime API query without guest startup |
| `original-main-full-memory-02/{stock24,stock23,cfw}` | Final native inputs, logs, diagnostics, `exports/` |
| `original-main-full-memory-audit-01/{stock24,stock23,cfw}` | Semantic/export audits of saved collections |
| `memory-export-legacy-audit-01/stock24` | Existing-plan compatibility audit without exports |
| `original-main-rtos-memory-inspection-01` | Initial linked-structure/selector checks |
| `original-main-rtos-memory-inspection-02` | Final strengthened provenance checks, unit log, 13 local dependency modules and source hashes |

Strengthened checks used saved material only; original main was not rerun. Proprietary RAM and binaries remain outside Git.

## Remaining connections

Full NVIC state, timer/peripheral state, and hidden core state have not been restored. Dedicated PSPLIM/MSPLIM APIs remain absent. Full RAM does not establish that resumption at arbitrary points is possible.

Next build a limited fixture explicitly combining this snapshot with public core state, and verify original PendSV save, task selection, restore, and exception return on actual M55. Then connect semaphore wait blocking → resume. Existing original-main SPI, external font-bank, integrated display, web installation, and recovery-readiness boundaries remain goals.

Overall completion remains **13/29=44.8%, scope v2**. No physical glasses/case access, firmware writes, or external publication occurred.
