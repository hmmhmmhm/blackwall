# Recovery watchdog ARM code and virtual IOM integration

bw-0142. Investigates recovery bootloader `boot_watchdog_feed()` without physical access.

## Code executed

`src/watchdog.h` from pinned g2-bootloader-patch candidate was checked against SHA-256 `26aa9fef14d1fe36b1581df1c20c5c1e0818451f8d855dbfa8810bf8311ed93b` and compiled unchanged for ARM Cortex-M55. A small C harness calls the function and records return and PRIMASK in a RAM mailbox. This is not complete stock main or recovery-manager execution.

Actual ARM instructions perform pointer CONT (0x281), read6 (0x602), and kick (0x301) through strict IOM7 MMIO. A host fixture prepares virtual PMIC config 0a/target 3c00 and a running timer. Pins 22/23, initial power state, frozen DWT value, and read6 status/reserved=0 are explicit mock conditions. This does not verify DWT time limits, long reception/scheduler, or physical bus latency.

## Difference found during integration

Initial integration stopped at read6. Pinned Renode IOM ReceiveData calls peer.Read for `min(4, remaining)`. Previous standalone PMIC test called Read(6) once and missed this difference. A bounded 4+2 read window was added to the optional timer model. Default model and rejection of holes without explicit mock remain. Recovery ARM branches/function body were not bypassed to pass.

01 failed before execution due to host power-node access error. 02 reached the 45-second limit after read-guard abort and the runner cleaned its container. 03 is a failure record identifying cause through diagnostic logs. Three cases in 04 were wall-time runs after correction. 05 replaced them with five cases at virtual 10 ms; 06 is final reverification with stronger checks of state before power request/query and read count. The initial unsupported DEMCR bit 8 fixture was also corrected to 0. Final logs allow only the known cache-size-clamp warning and reject other warnings/errors. Failures are not used as completion evidence.

## Final recovery-function tests

Private `simulator/recovery-pmic-feed-06/report.json` and each case's raw log/report are retained.

| Condition | Return | IOM commands | Kick | Restoration |
| --- | ---: | ---: | ---: | --- |
| Matching profile | 1 | 3 | 1 | Power request 0, debug restored, PRIMASK 0 |
| Target mismatch (3c01) | 0 | 2 | 0 | Power request 0, debug restored, PRIMASK 0 |
| Existing IOM power in use | 0 | 0 | 0 | Existing power 256 retained |
| Matching profile, PRIMASK 1 | 1 | 3 | 1 | PRIMASK 1 retained, power/debug restored |
| GPIO configuration mismatch | 0 | 0 | 0 | Power 0 retained |

Read consists of two peer calls and one repeated START. After the guest requests power off, host calls ReadStatus once to check model transition. This is not described as guest polling for off completion.

## Remaining scope

Full recovery boot/manager/long reception, bus-busy transitions/errors/timeouts, actual DWT/PMIC reset, physical stock restoration, and both-temple verification remain separate. This is not evidence of an installable combination. Overall product progress remains 13/29.

## Final reverification and preservation

After PMIC source changes, `pmic-timed-unit-05` 240 checks and `pmic-timed-main-03` three originals plus one default control were rerun. The three original inputs retained previous config 0a/target 3c00/strobe 1/Start 0 and next strict 0201. The 82 checks in `pmic-timed-verification-02/report.json` compare saved unit/native/feed raw results and current source snapshot, original main invariance, ARM ELF/pinned header, power request/settle, and debug preservation. No exact transcript archive comparison was performed. Independent GPT-6-family review feedback on power/time interpretation was incorporated.
