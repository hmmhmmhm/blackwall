# Regression Candidate: App State, kvTime, and Log Stack Propagation

bw383, partial E15/E16 progress. Producers of the extra four SRAM bytes retained from bw382 were identified using original code and observations in the same execution. **Five bytes propagate as app state 1 + kvTime zone 1 + CRC 2 + log-argument stack 1.** The difference oracle was derived from source and inputs without adding arbitrary allowed addresses. The candidate's app_state failure remains.

## Producers and actual values

| Location | Original 16 → regression 0 | Original-code evidence |
| --- | --- | --- |
| 0x200076b8 | App-state zone 16 → 0 | Test candidate changes `ldrb` at 0x4fab34 to `movs r0,#0`; existing `strb` stores it |
| 0x20006914 | kvTime record zone 16 → 0 | 0x4fad88/8c read state zone/timestamp as arguments and call 57a39c; 57a3a0 writes record+8 |
| 0x20006916–17 | CRC 0x58fe → 0x5b8d | At 57a3ae, original 4d0888 computes CRC of first ten bytes, seed ffff; 57a3b2 stores a halfword at +10 |
| 0x20052be0 | Low byte of log-argument word 16 → 0 | 4fadce signed-loads state zone, 4fadd2 stores to actual SP, and stored value is confirmed at 4fadd4 |

Record base is 0x2000690c, with type 3, padding, timestamp, zone, padding, and CRC. The original store call's key string is `kvTime`; this does not mean it is the same data structure as the BLE SMP slot key DB. Padding was preserved from the original initial record, while type/timestamp/zone and CRC were derived from source.

Original final 12 bytes: `0300000000f153651000fe58`.
Regression final 12 bytes: `0300000000f1536500008d5b`.

## Producer observations in original main

`probe_runtime_state_lineage.py` copies pinned inputs from existing captures and adds C# PC observations at four points. It reads actual registers, active TCB, Thread context, state, record, and stack word before/after the original caller's store call (4fad8e/92) and log-argument store (4fadd2/d4). It does not change instructions, branches, returns, PC/TCB/SP; added observation is recorded as a separate execution profile. Output does not overwrite saved source.

Each of two native runs, one original and one regression, confirmed four rows. Caller R0 was timestamp 1700000000 and R1 was 16/0 respectively; record updates matched these values and independent CRC. Actual SP for the log store was 0x20052be0; the word changed from 8 before store to 16/0 afterward. These occurred in the original ble_msgrx task and Thread context.

Both runs matched existing captures without observation in connection-report JSON values and complete initial/pre-ATT/final SRAM. This is equivalence for those two pinned profiles and observed items, not a general guarantee that PC hooks or read-only observation have no effect. It does not claim equivalence of all transient writes or all CPU/timing state.

## Independent comparison of original ARM function and CRC

`verify_runtime_state_lineage.py` checks source instructions/literals, original main SHA, executable pins, and log/JSON consistency. It then executes original 57a39c and CRC 4d0888 in isolated Unicorn M7: eight scenarios covering zone 0/16/24/255 × store API return 0/7. No broad memory-write hook is used.

Original ARM performs CRC calculation, independently compared with Python `binascii.crc_hqx`. Only logging flags and the storage API leaf are replaced with synthetic ABI; actual MRAM/NOR programming is not executed. Synthetic nonzero return 7 is preserved as original return 7, but the RAM record is already updated. Return 7 was not verified as a specific actual storage-device error code. Therefore RAM changes, API invocation, and a successful return alone do not establish persistent storage or retention across reboot. E07/E08 remain incomplete.

## Comparison assessment and preserved failure

The initial one-byte expectation and failure in `runtime-candidate-regression-comparison-01` are retained. New `derived-expectation.json` derives the five-byte difference from confirmed producers, input values, CRC calculation, and actual SP. A new comparison auditing existing unobserved original/regression captures with this oracle passed. This judges that **the intended defect's effects matched expectations**; candidate execution remains `passed=false`, with app_state as the failed check. The historical result was not rewritten as success.

Four negative mutations of observation material—CRC, SP, caller arguments, and pre-change record—were rejected even with consistent JSON/log/hash. The frozen checker's eight-scenario report and derived oracle were byte-exact. Existing candidate 9, native-contract 13, and progress-management 14 checks passed.

```sh
<private-python> tools/probe_runtime_state_lineage.py <original-stock24-time-capture> <new-observed-capture>
<private-python> tools/verify_runtime_state_lineage.py <simulator> <new-verification>
<private-python> tools/compare_runtime_firmware.py <original-capture> <regression-capture> <new-comparison> \
  --expectation <verification/derived-expectation.json>
```

Pinned original/regression observation paths are private `runtime-state-lineage-native-01/{original,regression}`, verification is `runtime-state-lineage-verification-02`, and new comparison is `runtime-state-lineage-derived-comparison-01`. Manifest, source, freeze, and negatives are in `runtime-candidate-lineage-research-01`. Proprietary binaries/SRAM remain outside Git.

Explanation of the current regression scenario's five-byte effect is complete. Other original/candidate profiles and display-change assessments for E15, and full execution/display/environment/recovery requirements for E16, remain. The next independent unit is investigating actual backing/commit and restart-consumption contracts for kvTime storage API 50bd7a → 577976. Natural GAF, full UI, and long-duration communication failure remain incomplete. All 16 criteria/status/evidence and API 3/6 are unchanged; overall is 5/16 = 31.25%. No physical work, external publication, or subagent invocation occurred.
