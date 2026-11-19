# Runtime Program Timeout Comparison Across Three Original Images

bw393. Previously unexecuted program-timeout cases for stock 2.3 and Faceclaw were verified using actual ARM main reset and device ATT input. **All three originals showed the same original poll failure 1 → NOR error 4 → adapter 0 bytes → partition 0 → FlashDB success 0, no actual NOR write, and an old-record read in a new process.** Stock 2.4 evidence was reused. E08 remains partial; overall progress is 6/16 = 37.5%.

## Same contract, different original addresses

Profile selection and `--all-originals` were added to `verify_runtime_nor_timeout.py`. Different main SHA values, functions, records, and TCB addresses were located in the original images and existing profiles; boot, actual returns, unchanged NOR, and new-reset conditions are checked consistently. The existing stock24 default report remains byte-exact.

| Profile | Actual return sequence | Runtime write | New main record | Subsequent GAF/CPU power boundary |
| --- | --- | --- | --- | --- |
| Stock 2.4 (reused) | 1/4/0/0/0 | Started 1, completed 0, bytes 0 | Previous version 1 | 0x58236c / 0x4956e2 |
| Stock 2.3 | Same | Same | Same | 0x57b014 / 0x4897fa |
| Faceclaw 38 | Same | Same | Same | 0x57b014 / 0x4897fa |

The new runtime fault uses the existing explicit host option that withholds the next program completion. ARM returns, branches, TCB, and IRQ were not forced. Values were read at the actual original Thread/original task return PCs; all KV/NV/LittleFS bytes remained unchanged while started 1/completed 0/pending WIP 1. The new record in RAM was distinguished from the old record in actual NOR.

The new process copied only the two completed NOR windows at CPU instruction 0. Its initial SRAM was byte-exact to the existing A5 initialization; prior guest SRAM was not imported. After reading the previous `010000002b2d37682000f018`, execution stopped at the existing strict CPDLPSTATE22 boundary. Restart CLI exit 1 and full boot false were retained.

The runtime upper app has not yet returned in any of the three cases. After the original GAF 153-byte read and 225-byte configuration, it stopped at the unsupported request `7c000402` boundary. Test success means the lost error, absent write, and restart read were reproduced and assessed; it does not mean firmware handled the error safely or full app recovery completed. Actual power loss and partial-bit programming remain unverified.

## Missing diagnostics in an older peer

The first stock 2.3 control consumed ATT and returned to the app normally, but the `pinned_gaf_profile` check failed. The older source run.py lacked a GAF diagnostic output function. Rather than assume missing values or delete the check, only the diagnostic function was extracted and connected from an existing verified stock24 capture. Its source capture SHA and exact function body are checked in each new control/fault. The entire current worktree run was not copied over the old template.

The new stock 2.3 control matched the missing-diagnostic prototype exactly in model/board, existing report fields, full SRAM at three points, and NOR before/after. Added diagnostics printed the actual pinned GAF state. The first prototype's native/check failure is retained in `runtime-nor-timeout-gaf-peers-01/stock23/control`; the final capture uses family02. Normal behavior was not rewritten as a success.

## Verification and reuse

There were six final new native runs: control/fault/restart for each of the two originals. The missing-diagnostic prototype is a separate historical run; the three stock24 control/fault/restart captures were reused with hash verification. Native runs were sequential.

The full audit has stock24 28 + stock23 30 + Faceclaw 30 = 88 checks. The peers' two extra checks cover diagnostic source SHA/body. The frozen audit report is byte-exact. Three negative cases consistently changing incorrect diagnostic values, diagnostic provenance, or hidden NOR errors through JSON/log/input hashes were each rejected by semantic checks. Fourteen progress-management checks passed; zero Docker containers remained afterward.

```sh
<private-python> tools/probe_runtime_nor_timeout.py <simulator> <writer-capture> <new-control> --gaf-profile
<private-python> tools/probe_runtime_nor_timeout.py <simulator> <writer-capture> <new-fault> --fault --gaf-profile
<private-python> tools/probe_runtime_kv_restart.py <simulator> <fault-capture> <new-restart> --retained
<private-python> tools/verify_runtime_nor_timeout.py <simulator> <new-audit> --all-originals
```

Pinned peer material is private `runtime-nor-timeout-gaf-peers-02/{stock23,cfw}/{control,fault}` and `runtime-nor-timeout-gaf-peer-restart-01/{stock23,cfw}`. The audit is `peer-runtime-nor-timeout-audit-01`, the freeze is `peer-runtime-nor-timeout-audit-frozen-01`, and lineage/diagnostic comparison/full pins are in `peer-runtime-nor-timeout-research-01`. The existing pinned local dependency wrapper was reused for dataless packages.

## Remaining E08 execution evidence

Comparison of actual per-original returns, damage scope, and restart results for the selected program timeout is complete for all three. Next apply the same existing erase tool to stock 2.3/Faceclaw with nonzero NOR patterns, withheld completion, and a new formatter to check remaining pinned erase scenarios. Do not rerun the completed stock24 experiment. Then audit full evidence for pinned write/erase failure, interruption, and data/version mismatch against existing E08 acceptance. Full E05/E06 services/app/reset are separate conditions.

The 16 acceptance/status/evidence criteria and API 3/6 were not changed. The 270-byte difference with normal erase observation on/off also remains unresolved. No physical device, BLE/USB/UART, flash/OTA, Astra/subagent, or external publication occurred.
