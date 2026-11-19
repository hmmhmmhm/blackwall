# Explicit clock trim input and original GAF configuration storage

bw-0353. The A2A2 read boundary after [bias storage](imu-gaf-bias-storage.md) was connected to an explicit virtual input. Original stock 2.4/2.3/Faceclaw each store **56 bytes of bias + 169 bytes of GAF configuration and derived values = 225 bytes**, then stop strictly at the first GAF service request `7c000402`. Service completion, sensor fusion, full initialization, and natural UI remain incomplete.

## Sources and level of confirmation

Both LE/BE headers at TDK ICM45608 commit `646f55a6ec119b59d9ebce47af660842b53e5506` define A2A2 as the 8-bit `SW_PLL1_TRIM`. The GAF structure declares clock variation as `int8_t`, and the EDMP memory description says that GAF field has the same format as SW_PLL1_TRIM. The original caller also reads one byte from A2A2 into GAF buffer+1. This test therefore verifies transmission and storage of that byte, not signed sensor-fusion results or physical PLL behavior.

- [TDK LE register map](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_regmap_le.h#L959)
- [TDK GAF structure](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp.h#L183)
- [TDK EDMP memory description](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp_memmap.h)

Five downloaded driver/register files were checked against the pinned commit's Git blobs and SHA256 and recorded in a private source manifest. Default 0 for the public GAF field is not evidence of the actual SW_PLL1_TRIM register reset value. **The physical glasses value, reset default, and physical clock accuracy are unknown.**

## Model contract

`gafClockVariationByte` was added to existing `BlackwallImuGafParameters`. Default -1 means unknown and rejects the A2A2 read. Specifying 0–255 requires selecting both the GAF fixture and configuration. This native input is nonzero byte `0x85`, not claimed as a physical or normal value.

In the declared profile after getter/power-save/the previous two services, start a one-byte read lease and return it through the actual indirect timer/read path. Reject overlapping selections, excess reads, and writes during an active read. Trim rereads return the same explicit byte; reset clears selection/read state. The GAF default 41-field read count remains 153 bytes, with trim reads counted separately. Orders outside the supported profile and general device compatibility of new CFW require separate verification.

The original setter stored 10000/2500 µs derived from actual accel/gyro ODR, the caller's period 20000 µs and mag interval 40000 µs, and the explicit trim byte. The model does not substitute for this calculation or service completion. The previous two completed services remain unchanged; the next request 2 at SRAM 0004 is rejected before application.

## Verification results

- 4,017 model unit cases: the existing 2,221 plus selection, raw return, reread, excess read, and reset for all 256 byte inputs, and rejection of invalid values/prerequisites.
- Three natural mains: one trim read, 56 bias + 169 setter = 225 byte writes, next request `7c000402`.
- Each native's complete 225-byte order and values were compared with the 45-transaction order from existing original setter source execution. Getter original buffer fields were also checked in actual guest SRAM.
- Original main hashes unchanged; compiled strict source was byte-identical outside the IMU component. No synthetic caller or changes to original branches, returns, or TCB were added.
- A stock 2.4 control without trim exactly matched prior bias-only CPU/full observations and stopped at A2A2.
- Parser rejected two out-of-range bytes, missing configuration, and four bootstrap conflicts; 13 existing runner semantic contracts passed. Plan contents were also confirmed identical after strengthening pinned source identity checks.

Saved captures were rechecked with frozen source without a new firmware run; result JSON was byte-identical. Source-only, virtual input, natural main, and physical verification remain distinct. Since GAF services remain, all of bw351 is deferred; E05/E12, overall 3/16, and API checklist 3/6 are not raised to complete.

## Reproduction assets

Under `~/Library/Application Support/Blackwall/simulator/` outside Git:

- `imu-clock-variation-source-01/manifest.json`: TDK source commit/blob/SHA.
- `imu-clock-variation-plan-01.json`: explicit virtual byte 0x85, pinned original/model/observations.
- `imu-clock-variation-main-01/{stock24,stock23,cfw}` and `imu-clock-variation-off-01`.
- `imu-clock-variation-unit-01/report.json`, `imu-clock-variation-source-01/planner-preflight.json`.
- `imu-clock-variation-source-01/verification-manifest.json`: source/result hashes and verification scope.
- `imu-clock-variation-source-01/native-verification-01.json`: saved original execution, complete writes, buffer, and control checks.

```sh
python3 tools/prepare_imu_ireg_candidate.py \
  "$HOME/Library/Application Support/Blackwall/simulator" <new-plan-json> \
  --gaf-configuration --gaf-clock-variation-byte 0x85

"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  "$HOME/Library/Application Support/Blackwall/simulator/imu-clock-variation-source-01/frozen/tools/verify_imu_gaf_storage_capture.py" \
  "$HOME/Library/Application Support/Blackwall/simulator" <new-check-json> --clock
```

The next unit is the original GAF on-demand requests 2/4 and mask/disable, ready wait, and failure contracts. Successful storage does not complete sensor fusion or justify returning ready unconditionally. No physical glasses access, installation, or persistent writes occurred.
