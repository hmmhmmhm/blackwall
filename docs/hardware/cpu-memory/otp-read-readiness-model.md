# OTP Read Readiness Model

Task `bw-0203`. Modeled only readiness before reading, according to the [HOST idle/OTP read contract](crypto-host-idle-contract.md). Three pinned ARM mains returned 0 from the readiness check and then stopped at actual word address `0x400c2340`. Neither that word nor other OTP contents were supplied.

## Contract and implementation

`BlackwallOtpReadReadiness` is a separate component handling only two addresses. The root fixture's `otpReadReadiness` defaults to null. When attached, the component's OTP/CRYPTO power owners must be the same objects as the root owners. Separate objects with the same mask are rejected.

- HOST `0x400c0a7c`: readable only when both OTP and CRYPTO are on and `hostIdle` is known. Choices are -1 (unknown), 0 (busy), and 1 (idle). The returned word is `0x3b8 | bit0`; other fields are an SVD reset-shaped assumption. The current original consumer checks only bit 0; other engine states are not verified.
- PTM `0x40014ac4`: requires OTP on and known `ptmBusy`, but does not require CRYPTO on. Other PTM fields assume reset 0; lock/error/failure states are not reproduced.
- PTM busy=1 requires an explicit read budget of 1..4096. It returns 1 N times and blocks the N+1th as an unsupported read. Only budget 0 is allowed for nonbusy profiles. This is an observation budget, not an added original timeout.
- Reset clears read counters while preserving immutable profile selection. Writes to either register, other widths, and OTP words remain rejected. The new component does not reset the power owner or create power state.

The CLI provides `--crypto-host-idle idle|busy`, `--otp-ptm clear|busy`, and `--otp-ptm-read-budget N` for busy. If both are unknown, the component is not attached. Selection requires an active CRYPTO scenario and retains existing active OTP, blank NVdb, and RX streaming prerequisites.

## Original execution results

| Condition | HOST/PTM reads | Readiness/word wrapper returns | Next block |
| --- | --- | --- | --- |
| Stock 2.4 / idle+clear | 1/1 | Readiness 0, word did not return | `0x400c2340` read, PC `560766` |
| Stock 2.3 / idle+clear | 1/1 | Same | Same address, PC `52f852` |
| Faceclaw 38 / idle+clear | 1/1 | Same | Same address, PC `52f852` |
| Stock 2.4 / HOST busy | 1/0 | Readiness 7, word 7 | CRYPTO off request `0x40021004=0x08000400` |
| Stock 2.4 / PTM busy budget 8 | 1/8 | Neither returned | Immediately before ninth PTM read, PC `56072c` |
| Stock 2.4 / PTM unknown | 1/0 | Neither returned | PTM read |
| Stock 2.4 / HOST unknown, PTM clear | 0/0 | Neither returned | Existing HOST read |
| Stock 2.4 / default unattached | 0/0 | Neither returned | Existing HOST read |

HOST busy error 7 is a return value computed by the original. Subsequent CRYPTO off was blocked because it is currently unsupported; do not treat it as successful cleanup or recovery. Under PTM busy the original loop actually repeated, but the function did not return an error or timeout. It stopped at the budget; no success branch, PC, return value, or delay was forced.

All mains match original bytes in the pinned bundle and executed from main reset. Existing synthetic identity/memory/power and logical SDR assumptions remain. This is not proof of full ROM/bootloader boot or actual power/busy timing. The three normal cases had 2,600 events, HOST busy 2,601, and PTM busy/unknown plus HOST unknown/default 2,599. All had capacity 4,096 and zero drops.

The new `OTP-read-ready-return` and `OTP-word-read-return` labels were preserved, while their removal and sequence renumbering were explicitly applied only for prefix comparison. The helper report lists them in `readiness_observation_points`. The existing 2,599-event prefix and NOR array/program/erase history were preserved for all conditions. Do not extend compact observations to a full instruction trace.

## Tests and evidence

There were 237 unit/regression conditions: idle 30, HOST busy 30, PTM busy 38, both unknown 28, independent HOST/PTM unknown 29 each, foreign OTP/CRYPTO identity one each, existing CRYPTO 30 and OTP power 21 regressions. They checked both HOST power conditions and independent PTM OTP condition, requested power not ready, read-only/width/word blocking, profile/budget/dependency errors, and counter Reset. Standalone power uses a local ready mock and is distinct from original execution. Four CLI prerequisite/budget errors were also rejected before output creation.

Outside Git under `simulator/`:

- `otp-read-ready-unit-02`, `host-busy-unit-01`, `ptm-busy-unit-01`, `unknown-unit-01`, `host-unknown-unit-01`, `ptm-unknown-unit-01`, `foreign-otp-unit-03`, `foreign-crypto-unit-01`, `crypto-regression-01`, `power-regression-01` — common prefix `otp-read-ready-`.
- `otp-read-ready-main-01/`: inputs, hashes, logs, and reports for the eight original conditions above.
- `otp-read-ready-cli-01/report.json`: four CLI rejections.
- `otp-read-ready-verification-01/report.json`: 218 final checks comparing current compiled model, unit/native logs and reports, original/derived hashes, observation addresses, projection, new boundaries/returns, budget, unknown/default, and NOR history.

Red was the absence of the new component type. In the first foreign-owner test, a global replacement mistakenly changed both root and component so their identities still matched. The fixture was corrected so only the component pointed to a different object. For a proper mismatch, the Renode platform loader could not handle the intended constructor exception and exited 133. These two negative tests were classified as expected platform rejections confirming the precise identity exception and no CPU start; exit 133 was also recorded in the report. They were not classified as successful normal execution, and initial failure logs were preserved.

A read-only review by an agent inheriting the parent model identified no Important/Critical product-code defects. The foreign fixture correction and independent unknown/default verification were incorporated. Astra was not used.

## Next boundary and limits

Later [INFOC window/consumer analysis](otp-window-consumer-contract.md) statically confirmed bank mapping and the eight-slot format. The statement below that the bank was unknown reflects the end of this model stage; actual word contents remain unknown.

Next statically analyze bank mapping of word `0x400c2000 + 0x340` and content requirements of the original upper-level consumer. The numeric offset alone does not establish INFOC/customer keybank or serial regions. No physical keys, identifiers, or calibration were read, and no definitions from another bank or arbitrary 0/FF were supplied. If a synthetic factory fixture is needed, separately verify provenance, format, scope, and abnormal-input handling.

There was no glasses scan/connection, RAM payload, OTP/fuse/security/MRAM write, OTA, or flash. Full factory initialization, whole boot, integrated display, and physical installation/recovery remain incomplete; product completion stayed 13/29, 44.8%.
