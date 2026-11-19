# Registered Candidate Execution and Comparison in the Device-Communication Runtime

bw382, partial E15/E16 implementation. Existing E04 raw-main registration was connected to the E13 device-input runner. **Actual ARM execution of a registered candidate and detection of an original app-state regression were confirmed; natural service initialization, full display, and complete E15/E16 were not.** No Astra or other subagent was invoked.

## Execution and audit contract

Specify `--firmware-manifest` and `--firmware-baseline` together in `run_runtime_connection_m55.py`. The baseline is the pinned original capture used to register that candidate. Both raw candidate and baseline must be inside the private simulator. Existing `firmware_candidate.py` declaration, hash, vector, registration baseline, and observer-anchor checks are reused.

New `runtime_firmware_candidate.py` also compares code points needed for device-communication observation against original 16-byte anchors. This is a limited check for that observation profile, not certification of the complete firmware ABI. Only candidate main and actual-length memory guard are substituted; model, board, SRAM/ITCM inputs, device events, and execution code are retained. CPU PC/TCB/SP, returns, and hardware checks are not forcibly changed.

The capture stores a candidate-registration copy and verified assets/reports from the registration baseline. Saved audits recheck these copies and do not require an external registry. Removing candidate metadata to impersonate stock, changing registration ID, runtime anchors, or memory length is rejected. Resupplying manifest/baseline during audit is also rejected.

```sh
<private-python> tools/run_runtime_connection_m55.py <simulator> <new-capture> \
  --case stock24 --att-time \
  --firmware-manifest <registration-folder/manifest.json> \
  --firmware-baseline <original-capture-used-for-registration>

<private-python> tools/run_runtime_connection_m55.py <simulator> <saved-capture> \
  --case stock24 --audit-existing --audit-output <new-audit>

<private-python> tools/compare_runtime_firmware.py \
  <stock-capture> <candidate-capture> <new-comparison>
```

The comparator requires the same profile, device inputs, model, board, and observer. The only permitted `run.py` difference is substitution of main-length protection. The original baseline must pass. Initial/pre-ATT SRAM, final SRAM, original connection reports, and individual execution assessments are compared. JSON value equality and file-byte equality are distinguished. SRAM differences record the total but report only the first 64 bytes; truncated results cannot pass as an exact expected difference.

Separate `--expectation` JSON can declare preplanned failed checks and SRAM differences. It does not change candidate `verification.passed=false` to true. Comparison and candidate-execution judgments are separate. Do not change model/inputs and compare the result as though it were a firmware difference.

## Actual ARM verification

| Run | Actual result | Limitation |
| --- | --- | --- |
| Stock 2.4 | Main reset → original hold → virtual device ATT → original BLE task → app/RTC, 25 checks passed | Normal GAF initialization/full boot incomplete |
| Existing E04 candidate | Independently registered candidate with 16 appended bytes; same path, 28 checks passed | App code is unchanged from original, so this does not validate a new user feature |
| Regression-test candidate | Changes original `ldrb r0,[r4,#4]` at 0x4fab34 in the candidate above to `movs r0,#0` with a two-byte change. Only the zone saved to the app becomes zero; existing RTC input is retained | Deliberate defect fixture for emulator verification, not a distributable CFW feature |

The first two runs are byte-exact in model, board, initial inputs, observer files, and complete initial/pre-ATT/final SRAM. Original connection reports have equal JSON values, but raw-byte comparison failed because top-level output order differed. The first comparison failure was retained and value comparison distinguished from byte comparison. Execution code differs only in main protection length substitution 3700068 → 3700084.

The regression candidate's native result is **exit 1, passed=false, with app_state as the only failed check**. IRQ, device connection, original task/stack, RTC commit/date, and existing error/unsupported-boundary checks remained intact. Initial/pre-ATT SRAM and connection-report values also match original.

A one-byte final SRAM difference in state zone was predeclared, but five bytes actually differed. In addition to original state `0x200076b8`, `0x20006914/6916/6917` and `0x20052be0` within the original app-task stack differed. Full producers/value provenance for the additional differences had not yet been demonstrated. **The expectation was not expanded after the fact, and comparison also remained passed=false.** Regression detection is distinct from completion of an explanation of its full effects. The follow-up was to trace those four bytes' producers/data flow from saved original code and captures.

## Verification and remaining work

- A failing-before result for the unsupported interface was confirmed before candidate build passed.
- Incorrect profile/hash/length and four runtime-specific anchors were rejected before output creation/execution.
- Five mutations—removing metadata, changing ID, length protection, anchors, or scenario while consistently updating capture hashes—were rejected.
- Nine saved audits retained existing true/false results and byte-identical reports for normal, regression, and unsupported GAF. Audits passed even when actual file opens of external registry and registration baseline were blocked.
- Existing candidate 9, native semantic-contract 13, and progress-management 14 tests passed. Frozen-tool audit results were separately retained.

The current runner supports only candidates matching its initial reset → hold observation profile. General early-failure reporting for candidates breaking that path, observation profiles for other ABIs/builds, and full UI/frame, natural services, reset, and storage scenarios require further work. One comparison command does not replace all E16 scenario execution/installation/recovery requirements.

Proprietary raw/SRAM, modified candidates, captures, and frozen tools are retained in private `simulator/runtime-candidate-research-01` and `runtime-candidate-{native,control,regression-native}-01`. All 16 acceptance/status/evidence criteria and API 3/6 remain unchanged; **5/16 = 31.25%**. There was no physical-device access, flash/OTA, external publication, or declaration of Goal completion.
