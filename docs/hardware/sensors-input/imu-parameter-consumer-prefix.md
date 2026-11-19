# First consumer segment of large IMU configuration and Faceclaw guard

bw349. Independently of GPU reference-profile design review, the path after natural main's IMU 153-byte getter was investigated. Main, full SRAM, and field map from the existing [getter/UI dependency analysis](imu-startup-ui-dependency-audit.md) were reused. **No new native run or IMU model change.**

## First helper does not consume the getter buffer

Stock 2.4 `4c2c86 → 554cca` and stock 2.3/Faceclaw `4b75ca → 520e72` receive a separate 12-byte vector and mode, not the getter's 168-byte caller buffer. Do not assume the first helper transforms all 153 bytes.

Original function requests six indirect SRAM writes:

| Address | Width | Relationship to original input |
| --- | ---: | --- |
| 0774, 0974 | 12 bytes each | Write input three-word vector unchanged |
| 0770 | 4 bytes | Extend mode's low byte to a word |
| 076c | 4 bytes | Modes 1/2/3 are 9999/4999/2499 respectively; other test values 500000 |
| 0780, 078c | 12 bytes each | Each input word signed arithmetic right-shifted by 5 |

42 scenarios per original, 126 total, used three signed/boundary vectors, modes 0/1/2/3/4/255/256, and bus results 0/fffffffd. Input vectors and SRAM were preserved; even with error status, all six requests continued and statuses were ORed for return. Physical units or actual bus-error application/rollback were not verified. Write callee is an explicit ABI stub in this test.

## Additional Faceclaw guard

Faceclaw executes a separate guard at `4b75be → 7d3338` before the helper. Its original hook body ran without observer/ABI stubs, confirming:

- Context pointer checks, magic `c0ffee6c`, and size `3f4` must match.
- Deadline at context offset 16c must be nonzero and its signed difference from current tick positive.
- Target mode byte below 4 is preserved; in other tested states it is cleared to 0.
- Modes 1/2/3 with valid context and future deadline can yield subsequent inputs different from stock's unconditional 0.

There were 252 scenarios: six modes, seven time/overflow boundaries, and six normal/pointer/alignment/magic/size/deadline controls. Context and tick are explicit synthetic inputs, not a claim that a lease was active in native main. Pointer checks are not guaranteed to safely handle all invalid addresses. Only declared input combinations were verified. The target byte and neighboring canaries were checked without changing SRAM.

## Prefix of the setter actually receiving 153-byte configuration

The next setter is stock 2.4 `5545be`, older/Faceclaw `520766`. The caller overwrites getter-result offsets 0/4/8 before passing this buffer. Original setter ran until before its next helper call. Register reads and indirect SRAM writes are ABI stubs; computations, branches, and field loads/stores are original instructions.

Three synthetic getter inputs and register 1b/1c values 0/6/8/10/ff were checked per image, 45 scenarios total.

- Tested codes 6/8/10 reached the next helper boundary after two register reads and 45 SRAM writes.
- Of these, **41 addresses/widths totaling 153 bytes exactly matched corresponding fields in the passed buffer**. This segment preserves and rewrites the remaining getter values without transformation. It does not restore caller-overwritten offsets 0/4/8 to original ROM values.
- The remaining four writes are addresses 0288/0290/028c/0818. For codes 6/8/10, words at 0288 and 028c were 1250/5000/20000 respectively, 0290 was 20000, and 0818 was 0. They are not named physical frequency or time units.
- Tested codes 0/ff returned `ffffffff` without SRAM writes. This does not claim every other code is rejected; track the error separately from caller success.

The first script incorrectly expected all codes to reach the next helper and failed. The original's normal error return was preserved and stop boundaries distinguished. Firmware was not modified and failure branches were not skipped.

## Verification and next boundary

Three reports from 423 original scenarios (126+252+45) and frozen-source rerun matched byte-for-byte. Fifteen directly loaded Python dependencies were frozen. Capture hashes from existing saved audit and raw extraction from pinned bundle were rechecked.

Private `simulator/imu-parameter-consumer-01/` preserves `probe.py`, `guard-probe.py`, `setter-prefix-probe.py`, `verify.py`, `verification-report.json`, and `imu-parameter-consumer-frozen-01/`. Full setter, initialization, and actual sensor calculation remain incomplete. ABI-stub tests are not counted as main progress.

The next boundary is the setter's helper stock 2.4 `55405c` / older `520204` and subsequent calculation/control order. Actual targets are recorded in the report. **This prefix alone does not justify filling the 153 bytes with arbitrary values.** Examine a limited initial-state profile only after checking full consumption/algorithm constraints and effects of explicit virtual inputs. Natural main remains before IMU02ae read; E05/E12 are partial. Overall 3/16 and API checklist 3/6 remain.

Follow-up [full GAF consumption and public defaults](imu-gaf-configuration-contract.md) confirmed 75 full-setter scenarios and frozen reruns, TDK source correspondence for 41 field addresses/widths/structure offsets, and documented defaults. Mode in this document corresponds to mag-bias accuracy; private variable name gyro does not mean offset 8's mag_dt_us. Natural main remains incomplete.
