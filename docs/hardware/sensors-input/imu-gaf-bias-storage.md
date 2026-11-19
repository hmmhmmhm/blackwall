# Natural main mag-bias storage and next clock-read boundary

Partial implementation and verification as of bw-0351. After the existing [GAF getter](imu-gaf-default-getter.md)'s 41-field, 153-byte read, original stock 2.4/2.3/Faceclaw successfully wrote 56 bytes across six mag-bias ranges. The next instruction in this profile is **a one-byte read of A2A2**, which stops strictly because its value is unknown. The subsequent explicit trim profile and latest 225-byte storage boundary follow the [clock variation contract](imu-clock-variation-contract.md). Service, FIFO sample consumption, full initialization, and natural UI remain incomplete.

## Model and supported scope

Opt-in `gafConfiguration` storage was added to `BlackwallImuGafParameters`. It defaults to false and requires an explicit GAF fixture. It is allowed only after existing getter and power-save completion and two existing service completions. This is the declared initialization profile of the three research images, not general support for arbitrary order or rereads in new CFW.

Storage is limited to the union of existing 41 fields and ten ranges confirmed in original setter/bias source. Writes crossing adjacent known ranges are allowed; if even one byte falls outside, the entire transaction is rejected before state changes. SRAM0004 service requests and A2A2 writes are not allowed. Original address and read epoch are bound to 7c headers and 7e continuation writes to prevent stale continuations after another indirect read. Reset initializes cursor and records. Original ARM code computes fields; the model stores bytes.

## Actual execution and limits

| Original write address | Length | Native value here |
| --- | ---: | --- |
| 0774 / 0974 | 12 bytes each | 0, same as original RAM bias vector |
| 0770 | 4 bytes | accuracy 0 |
| 076c | 4 bytes | original default 500000 (`20a10700`) |
| 0780 / 078c | 12 bytes each | 0, result of original signed shift |

Each image recorded 56 byte transactions. Existing GAF 153 bytes remain unchanged and completed service count remains two. Main binaries matched previously pinned originals, and the existing natural main path ran without synthetic callers or branch/return/TCB changes. Compiled strict source comparison checked no changes outside the IMU component. The stock 2.4 option-off control exactly matched existing getter-only CPU/full observations and made no 56-byte write.

Initial design assumed clock variation would be written. The first native stopped at `7ca2a2` after 56 bytes; reanalysis of the original caller identified a read-reg call. For example stock 2.4 `0x4c2c8c..0x4c2c98` reads address A2A2, length 1, into getter buffer+1. Support for the unexecuted clock write was removed. An arbitrary 0 was not returned as a physical register value. The failed capture/plan with initial expected 225 bytes versus actual 56-byte boundary was preserved.

## Reproduction and evidence

Paths below are under `~/Library/Application Support/Blackwall/simulator/` outside Git.

- Final plan: `imu-gaf-storage-plan-04.json`.
- Three natural mains: `imu-gaf-storage-main-02/{stock24,stock23,cfw}`.
- Disabled control: `imu-gaf-storage-off-01`.
- Model units: `imu-gaf-storage-green-02/report.json`, 2,221 passed including existing checks. Checks cover known ranges/crossing writes, full 8192-byte preservation, rejection atomicity, reset, and default disabled. Absent-class red is `imu-gaf-storage-red-01`.
- Saved capture inspection: `imu-gaf-storage-research-01/native-verification-01.json`. It checked actual 56-byte writes, original bias inputs, next clock-read caller, unchanged main, unchanged non-IMU source, and off exactness.
- Initial `green-01`'s 2,222 cases tested the earlier model including removed clock writes; they are not mixed into current verification counts.
- `plan-01` was rejected before execution due to an incorrect audit reference. The first native of `plan-02` passed execution but failed expected semantics. `plan-03`'s invalid MMIO width 3 was rejected before execution. Final plan04 distinguished actual MMIO width 4 from command length 3 and was verified.

Plan generation creates the current model's bias-only profile; audit of the historical plan04 capture uses preserved frozen source. Output must use a new path.

```sh
python3 tools/prepare_imu_ireg_candidate.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-plan-json> --gaf-configuration

"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  "$HOME/Library/Application Support/Blackwall/simulator/imu-gaf-storage-research-01/frozen/tools/verify_imu_gaf_storage_capture.py" \
  "$HOME/Library/Application Support/Blackwall/simulator" <new-check-json>
```

Next identify A2A2's meaning, value source, and supported virtual input contract, then verify passage of the original read value to the GAF setter. Do not mark all of bw351 complete before GAF configuration/services finish. E05/E12, overall 3/16, and API checklist 3/6 remain. No physical access, flash, or persistent writes occurred.
