# Final acceptance of bootloader validation 1–4

2026-11-17 · bw-0583. All **12/12 conditions, 100%**, of the approved `bootloader-validation-v1` were met. This is the acceptance rate for the virtual verification scope below, not 100% fidelity for the entire chipset, actual Boot ROM execution, or physical installation safety. The denominator of 12 was not changed.

## Evidence by condition

| Condition | Verified result | Primary evidence |
| --- | --- | --- |
| BV01 | Pinned inputs, boot-only execution, fault/unsupported classification, and rejection tests | boot-validation-audit-bw554-01 |
| BV02 | Pending success, ROM error, zero/one-word interruption, and selection after new original reset | pending-metadata-cycle-audit-bw573-03 |
| BV03 | Original SP predicate; distinguish actual handling of invalid vector from CPU fault | boot-sp-audit-bw560-01 |
| BV04 | Original patched reset→manager→worker→main, existing fallback retained | b0-power-recovery-audit-bw576-02 |
| BV05 | Same-board UART2 normal/error/no-input/timeout retry→main | dwt-auth-main-audit-bw579-02 |
| BV06 | Same-board original UART/API3, corrupted 16-byte restoration twice→RESULT/main, and stock control | same-board-mram-audit-bw582-03 |
| BV07 | Virtual MRAM program ABI, alignment/range/IRQ, success/error | mram-interruption-bw555-01 |
| BV08 | Pass partial program result to new reset to check boot selection and risks | restore-interruption-reset-bw565-01 |
| BV09 | Block prohibited direct stores before writing; protect boot/metadata/neighbors | protected-mram-replay-bw563-01 |
| BV10 | Restore full virtual stock application hash→new boot/main/frame | full-main-restore-audit-bw564-05 |
| BV11 | Original main callback over 39 pages/original verifier, full 4 MiB stock hash→new boot/frame | main-driven-boot-audit-bw571-02 |
| BV12 | Ten pinned assets, task-specific combinations/unsupported rejection, full-stock repetition | bootloader-matrix-audit-bw574-05 |

All primary evidence is under `private:simulator/`. The 34 final comprehensive audit checks covered each primary report's pass/explicit checks, document/evidence presence, scope boundaries, indications that ROM/physical behavior was unverified, preservation of past failures, and recent cleanup. The audit rerun from `/tmp` using saved source and documentation snapshots also passed 34 checks. These 34 are not presented as a count of new hardware execution tests. The independent 71-check audit, 41 native C# checks, and host tests for the latest actual recovery are in the [separate results](same-board-mram-recovery-results.md).

## Supported profiles and scope

The existing combination table's `synthetic-chip23-trim0` remains unchanged. The new worker/authentication/recovery was verified by these executions **only on synthetic B0/trim1, current 2.3.2.14 boot + main from the same bundle**. Explicit assumptions include DWT 10 MHz, PMIC known-running/read-hole mock, synchronous IOM7 off response, and a 16-byte functional ROM. The [additional profile record](../data/bootloader-additional-profile-evidence.json) separates exact boot/main/model SHA and operation scope.

The existing planning checker was not changed to automatically allow the new profile. Physical/unknown/Faceclaw cross-combinations are not promoted to supported. Same-board main entry with original stock 2.3 boot was confirmed, but this evidence does not claim full UI/frame completion in that profile. Full stock screen/restoration evidence is a separate result for the pinned 2.4 profile. Features of one model are not automatically aggregated into another.

## Failures found and remaining limits

- If apparently valid SP/reset vectors remain, the original boot can enter even an incomplete main. We cannot claim that original boot safely rejects every corrupted image.
- Main selection was possible even when only the first word of the pending marker was erased; the original path that discards a ROM write failure and requests POR was also confirmed.
- The self-overwrite failure when restoring resident boot itself was preserved. It is distinct from subsequent virtual full-stock restoration through the **original main callback**.
- ROM error 7 is converted to 08000107 by the stock wrapper. Entry into main after an error is not counted as successful restoration.
- Actual Boot ROM, MRAM program physical behavior/power interruption, factory INFO1, case relay, left/right temples, and physical full-stock recovery were not verified. Tests that passed the resulting state to a new virtual cold reset instead of actual reset propagation were also explicitly distinguished.

The current tools can therefore be used for **bootloader regression under pinned profiles, original branches/protocols, and declared virtual recovery/failure verification**. They must not be used to decide whether installation on physical glasses is possible. This goal involved no physical access and created no permission for subsequent flashing.

## Reproduction and cleanup

From the project root, the following are read-only audits of saved evidence. The outputs use new private paths that do not yet exist.

```sh
python3 -B tools/audit_same_board_mram_recovery.py "$HOME/Library/Application Support/Blackwall/simulator/recheck-mram-recovery-01"
python3 -B tools/audit_bootloader_final_acceptance.py "$HOME/Library/Application Support/Blackwall/simulator/recheck-boot-acceptance-01"
```

The audits alone do not rerun original firmware. A new native execution requires pinned Renode/Docker and private canonical assets and is run separately as follows. It uses no physical communication.

```sh
python3 -B tools/run_same_board_uart2.py --boot-retention --dwt --watchdog-read-holes --watchdog-initial matching-running --recovery recover16 --allow-checksum-sram --synchronous-iom7-off --bounded-main-rom --corrupt-main16 good-cont "$HOME/Library/Application Support/Blackwall/simulator/recheck-native-recovery-01"
```

The final comprehensive stage created no new native build or firmware copy. Receipts for termination of the latest 12 owned jobs and cleanup of 36 duplicate files totaling 73,462,296 bytes were rechecked. Canonical inputs/hashes, execution models/sources, failure diagnoses, wire/logs, and audits are retained. Upstream or existing work was not repeated to inflate test counts. Earlier conservative recovery flags were not overwritten; the latest audit's verdict and scope were stated explicitly.

Final evidence: `private:simulator/bootloader-final-audit-bw583-03/report.json`, independent rerun 04/report.json. Initial pre-completion snapshots 01/02 are also retained. [12-condition progress table](../data/bootloader-validation-progress.json) · [original plan](bootloader-validation-plan.md).
