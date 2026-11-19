Final [bootloader validation 1–4 acceptance](bootloader-final-acceptance.md): **12/12 conditions, 100%**. Original UART/API3 nonzero-length virtual MRAM restoration twice→main and error/stock controls confirmed. Original Boot ROM and physical installation safety certification are separate; percentages below are historical.

Latest [approved RAM-code execution and repeated power responses](bounded-recovery-execution-results.md): read-only LOAD/RUN→RESULT/main and error/tamper/stock controls confirmed. Nonzero-length MRAM recovery integration remained, 11/12=91.7%.

Latest [recovery LOAD and execution-protection boundary](recovery-load-boundaries.md): original CRC/READY and error/RLSD confirmed. SRAM execution policy/IOM7 off-lifecycle model remained, BV06 incomplete, 11/12=91.7%.

At that point [progress table](../data/bootloader-validation-progress.json): **11/12=91.7%**, BV05 complete via [DWT and same-board authentication](dwt-auth-main-results.md). Remaining BV06 was actual recovery-command completion→main and original control. Lower percentages are earlier history.

Latest [boot retention/authentication response](boot-retention-auth-results.md): three original WFI/returns and actual OKAY/CONT/RLSD confirmed; watchdog DWT boundary, BV05/06 incomplete, 10/12=83.3%.

Latest [same-board UART2 authentication decisions](same-board-uart2-auth-results.md): original claim/rejection under normal/error/partial-timeout retry confirmed; pre-OKAY CPDLPSTATE 22 boundary, BV05/06 incomplete, 10/12=83.3%.

Latest [B0 power initialization/original worker integration](b0-power-recovery-results.md): natural worker/HELO/main path obtained; BV05/06 authentication/recovery commands incomplete, 10/12=83.3%.

Latest [INFO1/B0 alternative research](recovery-info1-contract-results.md): synthetic B0/trim 1 original reset stopped at SIMOBUCK1, worker/auth not entered. 10/12=83.3% retained.

At that point [progress table](../data/bootloader-validation-progress.json): **10/12=83.3%**, remaining conditions same-board authentication/recovery. Latest [version matrix/unsupported rejection/restoration repeat](bootloader-compatibility-results.md). Earlier percentages are history.

Earlier [progress table](../data/bootloader-validation-progress.json): **9/12=75.0%**, full validation in progress. See [pending metadata/reset verification](../research/pending-metadata-cycle-results.md) and [virtual full-stock restoration](main-driven-boot-restore-results.md). Percentages below reflect their respective times.

Earlier investigation: [existing stock OTA and main-write path](../research/upstream-independent-restore-review.md). Source/actual gate 12 conditions identified a follow-up candidate; no new ARM/OTA execution yet. 7/12=58.3% retained.

Earlier boot self-restoration: [resident code lifetime results](boot-self-restore-results.md). Stock boot body→screen succeeded but full stock incomplete. 7/12=58.3% retained at the time.

Earlier: [full main restoration and interruption reset](full-main-restore-results.md), then **7/12=58.3%**. The 5/12 and 3/12 below are prior verification history.

Earlier protection fix: [direct MRAM store verification](../hardware/cpu-memory/mram-direct-store-protection.md). A post-change observation-hook defect reopened BV09 temporarily; write-boundary blocking and ARM regressions restored completion. Then 5/12=41.7%.

Earlier follow-up: [upstream/trim review](bootloader-upstream-trim-review.md), [vector/MRAM/restoration boundaries](boot-vector-and-restore-boundaries.md). Then 5/12=41.7%; 3/12 below is initial verification history.

# Bootloader validation results

2026-11-17 · bw-0554/0555. First verification of items 1–4 approved by the user. [All 12 conditions](bootloader-validation-plan.md) and [current progress](../data/bootloader-validation-progress.json) remain. **Acceptance was 3/12=25.0%; full recovery verification was in progress.** Obtaining each stage's research/test results differs from completing integrated recovery.

## 1. Dedicated original boot scenarios

`tools/run_boot_validation.py` permits only pinned stock 2.4 and research-patch SHAs. Without changing canonical source it explicitly changes only marker or main vector in private inputs. Existing `run_original_boot_screen.py` SHA gate remains. Source/execution profiles, input mutations, native observations, image SHAs, and owned journals are retained. Execution starts at bootloader reset without forcing PC/return/TCB.

| Scenario | Actual result | Interpretation |
| --- | --- | --- |
| Cleared-marker normal | Reused two prior final cold original boot→main→screen captures | Not rerun redundantly |
| Pending `55555555` | Boot manager→marker load→ROM power reactivation request, model stop at `0x41bdbe`, `0x40021014=3f` | Not bootloader update success/rejection |
| Corrupt marker `55555554` | Original boot handoff→main reset, fault/guard 0 | Original equality treats it as non-pending. Not general metadata-integrity verification success |
| Main SP=`dead0000` | PPB guard blocks `0xe001e300` write at `0x41ca00` before handoff | Safe vendor rejection undetermined; unsupported state is not recovery success |
| Main reset=`90000001` | After actual stock handoff, CFSR 1/HFSR 40000000 and CPU fault | This input was not safely rejected in advance; do not generalize to every invalid reset combination |

Pending `0x40021014` is **MEMPWREN ROM power bit 5**. This corrects the earlier broad commentary description as cache/MRAM. Pinned Ambiq header has PWRENROM mask 20/PWRSTROM mask 80; HAL in AUTO mode enables ROM power then waits for status. Current frozen MemoryStartup supports 3f→1f disable but rejects 1f→3f enable. Next verify ROM-power lifecycle as a separate functional contract; do not infer possession of actual Boot ROM bytes or MRAM programming permission.

## 2. Natural execution of recovery patch: worker disabled under guard

Research boot SHA `5ac1b02d…`, 159744 bytes, and stock main ran from actual reset. It reached **patch manager→stock flag→stock handoff→main reset**, with unchanged boot/main bytes and guard/CPU fault 0. UART2 worker hits were 0.

Additional native observations narrowing the cause showed the same fallback/main result. Actual SRAM just before the guard:

| Location | Actual value |
| --- | --- |
| UART2 handle `20000494` | Non-null `20024638` |
| Pin table `20000498` | Expected `434220` |
| RX callback `200004a4` / awake `200004a8` | 0 / 0 |
| Pre-power callback `20026e44` | `42d91b` |
| Post-power callback `20026e48` | `42d925` |

Pinned patch `boot_task_then_flag` requires both power-callback slots 0 to proceed to UART2 wake/worker creation. Actual branch is callback check at `4354f6`→fallback `435500`, wake path hits 0. Source, actual branch, and SRAM agree. A separate isolated test with callbacks set to 0 alone could not establish recoverability of this natural path.

**Current candidate returns to normal stock main but does not provide a recovery interface under these 2.4 virtual initialization conditions.** This is not a claim that all actual hardware/2.3 always behaves so. Callbacks were not erased and guard was not ignored. Next analyze original callback registration timing, ownership, function effects, and hook/protocol designs that safely coexist. If changes are necessary, discuss a concrete design separately from verification goals.

## 3. Virtual MRAM interruption: limited ARM writer experiment passed

Optional atomic 32-bit-word prefix interruption was added to the existing M55 resident-writer fixture. Original ARM context wrapper→RAM recover.bin→original MRAM adapter executes; ROM programming/time/UART and others are existing explicit functional models. This is not silicon partial-bit/power-collapse modeling. Existing normal/error evidence was reused, with one new normal control for the fixture change.

| New condition | Observation |
| --- | --- |
| 512-byte normal control | Actual RESULT 0, context restored, full 4 MiB MRAM matches expected |
| Four interruptions at 0/16/256/272 bytes | No RESULT/context return; only corresponding prefix written; 16-byte vector/boot/metadata/neighbors preserved |
| MRAM from each interruption passed to four fresh CPU writer calls | Each writes 512 bytes, RESULT 0, same final MRAM SHA |

Nine new native contracts passed. Rerunning after interruption is **new CPU execution at a saved RAM invocation boundary, not boot reset**. It therefore did not yet prove BV08 selection after boot reset or complete update recovery. Write range is 512 bytes of main body from `438010`. Full main, vector commit, boot restore, and full-stock recovery were not performed.

Separate full 4 MiB MRAM before/after comparison was performed. All normal/retry final SHAs are `5ba7a239665f79b800a0d170511d6a13f300dd789bb274190c53226130c2dafe`. This is a **small fixture MRAM with damaged main vector 0**, not an official full-firmware SHA. Range protection is a virtual guard for this fixture, not proof of actual ROM permissions.

## 4. Stock restoration and version combinations

`tools/check_virtual_restore.py` and five tests distinguished main-byte match, full-stock-byte match, unconfirmed inventory, and reboot verification. Actual boot/main hashes from native patched-silent yield main matching stock but boot patched, hence full-stock=false. This classifies byte state after normal boot, not an actual restoration operation.

| Combination | Current verification |
| --- | --- |
| Stock boot 2.4 + stock main 2.4 | Two original boot→screen cold runs, existing evidence |
| Patch boot 2.4 + stock main 2.4 | Two natural main entries here, no worker entry; authentication/recovery unverified |
| Patch boot 2.4 + Faceclaw38 | Existing 16 isolated handoff conditions at specified call sites. Not natural recovery/boot completion |
| Patch boot 2.3 / recovery 2.3 | Pinned local artifact profile exists. Natural boot/restoration not verified here |
| Boot 2.3 / recover 2.4 or inverse | Different pinned hashes/profiles and MRAM bindings. Existing recovery-set checker rejects mixing |
| Physical case/both temples/full stock | Unverified; virtual success not carried forward |

Existing `recovery-artifact-profiles.json` and `tests/test_recovery_set.py` evidence for correct pairs and bidirectional writer/key mismatch, missing/corrupt rejection were reused. Standalone restore-hash checks or host byte copies alone do not complete BV10/BV11. Integrated restore reboot cannot be verified until current worker guard and ROM/update boundary are resolved.

## Tests, audit, and failure preservation

- Host tests: boot runner 8 + existing original runner 14 + recovery writer 6 + restore 5 = 33 passed.
- Native boot: 55 checks across final six scenarios for source/image/classification/guarded fallback/owned jobs passed. Two normal original cold runs were reused.
- Initial three cases omitted existing MSPI1 retention connection in the new runner, stopping too early at power guard. A separate regression test was added and connection restored. One more had an exporter error reading nonexistent GPU Mask property. All original logs/source remain, distinct from final six.
- Original reset path/corruption-classification tests are actual ARM execution, distinguished from host/mock, reference functional model, and physical safety certification.

Evidence: private `simulator/boot-validation-audit-bw554-01/{audit.py,report.json,*tests.log}`, each `boot-validation-*-bw554-*` capture, `simulator/mram-interruption-bw555-01/{experiment.py,summary.json,audit-and-cleanup.json,restore-assessment.json}`. Native body/current CPU observation originals remain in each capture's source/log/report.

After verification, reproducible MRAM/SRAM duplicates and failed-exporter inputs totaling 102,865,176 bytes were cleaned up. Original baseline captures, input manifests, new model/runner source, actual logs, final 512-byte body, hashes/change ranges, and reconstruction method remain. Other work's assets were not removed. Nineteen journals for these tests confirm owned container absence after termination. No physical device, BLE, serial, browser, subagent, or external publication occurred.

## Follow-up bw-0556: ROM power and actual ROM-call boundary

Pinned HAL/header confirmed ROM power enable/status, and optional ready/stuck profiles were added to existing `BlackwallMemoryStartup`. Default -1 retains previous re-enable rejection. Existing original boot→screen frozen source/profile were unchanged. Pure C# 26 conditions in `tools/verify_rom_power_lifecycle.py` checked legacy rejection, disable/ready/stuck/status, unknown bit/direct status-write rejection, and reset. Initial unimplemented RED and final GREEN remain.

Two new private pending profiles reached **original reset→boot manager→pending handling→original MRAM wrapper→ROM entry `0200ff20` call**. Both stopped in Renode backend because executable ROM is absent at that address; boot/main SHA unchanged, guest CPU fault/memory-policy/guard 0, main entry 0. ROM-entry arguments correspond to key 12344321, operation 1, SRAM source 20022d68, MRAM destination 7fe000, word count 4. No ROM code executed or MRAM written.

Original capture classification was `stopped-unclassified`. Classifier later added `unsupported-rom`, requiring **both native-log unmapped-ROM execute diagnosis and PC 0200ff20**, and reclassified it in a separate 16-condition audit. Raw reports were unchanged. Host boot classifier grew to nine conditions; prior 34 passed together with existing 14 + writer 6 + restore 5.

Both ready and stuck proceeded to the ROM call. Source `42e81a` calls ROM power enable but does not check its return before ROM dispatch at `42e828`. Instruction counts differ by 79,997; neither full instruction-stream identity nor attribution of the entire difference to one loop is generalized. Stuck was not classified as normal power readiness or write success.

Static callback tracing also matches actual native observations. Original initialization `41d06a/41d06e` registers two callbacks from literals `41d18c/41d190` in the table. Thus setting callbacks to 0 in the model to solve non-entry to worker would bypass original initialization effects.

Additional evidence: private `rom-power-{red,green}-bw556-01`, `rom-power-followup-bw556-01/{report.json,callback-registration.json}`, `boot-validation-pending-rom-{ready,stuck}-bw556-01`. All 23 owned native journals/containers confirmed terminated and cleaned. New ROM power tests created no host build/compiler outputs; new pending inputs/full image dumps were removed by existing runner after hashing. Source/log/analysis remain. Integrated acceptance was still 3/12; next review scope for connecting virtual ROM/MRAM functional model to the full board and ownership of original callbacks. Do not assume possession of original ROM or physical installation approval.

## Follow-up bw-0569: stock main writing and error returns

[Execution/audit results](stock-main-mram-probe-results.md): original main adapter/buffer ran with a synthetic M55 caller, checking 4 KB normal write, ROM error, readback corruption, alignment rejection, and ROM power boundary. Buffer returned 0 even on ROM error/0 bytes; separate original memcmp detected mismatch. Upper OTA callback retained three records for JEDEC, missing FPU initialization, and unsupported clock and remained incomplete. Not counted as natural OTA/full stock. After cleanup: independent 181-check audit, input unit 2 passed, ten owned jobs terminated, 42,604,100 bytes cleaned. Overall 7/12=58.3%, BV11 partial.

## Follow-up bw-0570: upper OTA callback and original verifier

[Clock/ITCM connection and actual results](stock-main-ota-callback-results.md): all three original callback normal/ROM-error/corruption cases returned normally and swallowed errors. Original OTA verifier normal returned 0; two errors detected actual readback/comparison mismatch then stopped at unsupported RTC log. Initial registration failure and error boundary without observer were retained. After cleanup: 169 audit, prior 181 regression, four units; eight owned jobs terminated/29,888,992 bytes cleaned. Full stock incomplete/overall 7 of 12. Next check full boot-footprint restoration via original main path.

## Follow-up bw-0571: virtual full-stock restoration complete

[Actual original-main-path results/independent audit](main-driven-boot-restore-results.md): 39 pages/159744-byte boot footprint restored via original callback/original OTA verifier, with full 4 MiB SHA 8e0e4761… matching virtual original. Actual MRAM→fresh stock boot reset/main/576×288 frame also passed. Boot/main/all modified persistent-area hashes plus reboot complete BV11, overall 8/12=66.7%. Synthetic tail 0, diagnostic caller, and functional ROM model; not physical/natural BLE OTA/same-board authentication certification. Default 4 KB normal/ROM-error regression/post-cleanup 89 audit/unit 12; four owned jobs terminated/28,067,197 bytes cleaned. Existing resident self-overwrite failure retained.

## Follow-up bw-0572: actual 16-byte pending ROM request observation

[Original request and clear/reset contract](pending-boot-rom-request.md): pending ready/stuck observed 7fe000 FF×16/four words/key/op/source/IRQ, exact to existing-run raw JSON. Original clear function discards write return status and calls SWPOR (40000008, D4). ROM/reset execution and virtual write were not performed; retry remains an expectation. Read-only 16-byte observation/25 independent audit/unit 11; two owned jobs terminated/15,099,818 bytes cleaned. BV02 partial/overall 8 of 12; next explicit persistent state/virtual ROM+reset integration.

## Follow-up bw-0573: virtual pending-marker lifetime complete

[Nine actual runs/boundaries/independent audit](../research/pending-metadata-cycle-results.md): declared 16-byte virtual ROM success/error/0- and 1-word interruption/stuck, original SWPOR store/actual result state→fresh boot selection confirmed. First word FF alone allowed main entry; ROM 7 repeated pending/POR twice. Not actual ROM/POR propagation or valid full OTA image installation. Default MMU/code protection identical; C# 13/host 11/post-cleanup audit 105; 14 owned jobs terminated/86,749,067 bytes cleaned. BV02 virtual condition complete, overall 9 of 12.

## Follow-up bw-0574: version combinations and supported-restoration repeat

[Scope and independent evidence](bootloader-compatibility-results.md): ten pinned artifacts/nine pairs; among 24×7 operations, eight verified allowed/160 rejected; unknown/source-only/physical rejected. Existing writer/key cross-rejection reused. New 2.4 full stock 39 pages/original verifier/full MRAM and fresh stock boot-frame repeat matched; full runtime SRAM not exact. Matrix 11 + restoration 41/regression 49 independent audit, checker unit 3/negative 5. Two owned jobs terminated/19,546,373 bytes cleaned. BV12 complete, 10 of 12. Other versions, physical devices, and same-board authentication/recovery remain unverified.
