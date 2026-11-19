# Optional OTP Power Response

Task `bw-0199`. Following the [OTP power request contract](otp-power-request-contract.md), optionally connected an OTP owner to the shared DEVPWREN/DEVPWRSTATUS bank. Actual OTP bytes, fuse writes, security settings, and the crypto engine were not implemented.

## Contract

`BlackwallG2StartupFixture.otpPower` defaults to null, retaining existing request blocking. Attachment requires the shared ADC/GPU bank, mask=`0x08000000`, and offProfile=-1. Owners with other masks or off support are rejected. Existing generic power-owner active/stuck-off profiles are reused.

Shared request/status reads OR the OTP bit with other owners. A request write invokes the relevant owner only when there are no reserved bits and at most one domain changes. Simultaneous changes, unsupported CRYPTO, and reserved bits are rejected before any owner changes. Re-requesting the same full word does not restart state. Normal requests require the existing buck-active condition.

Active returns on at the first status observation after request; stuck-off retains the request bit but status remains 0. These are explicit mock responses, not measured physical power-up time or stability. Reset clears owner request/status and diagnostics. Turning off OTP that is already on is unsupported. Canceling a pending/stuck request that has not yet turned on is a generic owner's mock transition, not an actual OTP power-down procedure.

CLI `--otp-power-response active|stuck-off` requires explicit blank NVdb and RX streaming scenarios. Unselected means unknown. This option does not connect to or manipulate power on an actual device.

## Original execution

| Condition | OTP caller return R0 | OTP status | Next block |
| --- | --- | --- | --- |
| Stock 2.4 / active | 0 | on | `0x40021004 = 0x08200400` |
| Stock 2.3 / active | 0 | on | Same CRYPTO power request |
| Faceclaw 38 / active | 0 | on | Same CRYPTO power request |
| Stock 2.4 / stuck-off | 4 | stuck-off | `0x40014ac4` PTMSTAT read |
| Stock 2.4 / unselected | Not reached | No owner | Existing `0x08000400` OTP request |

Active request/status were `0x08000000`, with one request and one response. UART1 `0x400` was preserved, and the next CRYPTO request also retained the OTP bit. CRYPTO enum 23 remains unsupported. The original 100 µs delay, status check, and return in the OTP call were not skipped. Delay branches and the unique caller-return instruction were compared with original bytes, but are not evidence of actual clock measurement.

The stuck-off caller received error 4. As previously established statically, it proceeded without checking that error and was blocked on OTP PTMSTAT read. Safe fallback, power-down, and recovery success therefore remain unverified. OTP off was not allowed and PTMSTAT idle was not arbitrarily supplied.

Original main matches bytes extracted from the pinned bundle. Main reset entry and existing synthetic identity/memory/power and logical SDR conditions were retained. PC, branches, returns, and delays were not forced. NOR array/program/erase history and the prior 2,596 observations were preserved; active/stuck added one unique OTP caller return for 2,597 events with zero drops. Unselected had 2,596 events and zero drops with the same board and stop boundary as before. Compact observations are not a full instruction trace.

## Tests and evidence

There were 145 unit/regression conditions: active 21, stuck 21, unknown 1, MSPI shared-power 23 and RX streaming 79 regressions. Standalone successful requests use a local mock supplying ready directly and are distinct from native acceptance of a normal shared-bank request. Tests covered reserved/simultaneous changes, UART1 retention, unknown default, off rejection, Reset, invalid owner, and missing bank. OTP RNG register reads also remain rejected. Two missing selection prerequisites were rejected by the CLI before output creation.

Outside Git under `simulator/`:

- `otp-power-unit-02`, `stuck-unit-01`, `unknown-unit-01`, `mspi-regression-01`, `rx-regression-01` — common prefix `otp-power-`.
- `otp-power-main-02/` — assets, hashes, logs, and reports for the five native conditions above.
- `otp-power-cli-01/report.json` — two CLI rejections.
- `otp-power-verification-02/report.json` — 132 final checks comparing current core/full compiled model, unit/native logs and reports, original and derived asset hashes, unique return instruction, event projection, unchanged NOR history, state, next guard, and default preservation. The initial 130 checks were preserved.

Red was absence of the otpPower constructor argument. The first unit failed because I incorrectly assumed `0x40020000` was OTP, but an existing different device allowed a read there. Comparing SVD OTP base=`0x40014800` and RNG offset=`0x2a0` corrected the test to `0x40014aa0`. Existing behavior of the other device was not changed.

The first native `otp-power-main-01/stock24` failed prefix comparison because a common power-function epilogue hook recorded 969 returns from other devices too. It had 3,566 events and zero drops but was not adopted as final passing evidence. Host observation was narrowed to one unique OTP-caller return point and rerun. Guest flow and peripheral model were unchanged.

A read-only review by an agent inheriting the parent model reported no Important/Critical defects. It incorporated the distinction between ready mock and native execution, physical off and cancellation, and original-byte comparison of the unique observation address. Astra was not used.

## Next steps and limits

Next investigate CRYPTO power enable/status and additional readiness conditions in source and original code. An OTP-on response does not prove readiness of the crypto engine, keys, cryptographic operations, or factory data. Distinguish crypto power from crypto register/engine implementation, and block unknown areas.

There was no glasses scan/connection, RAM payload, OTP/fuse/security write, MRAM, OTA, or flash. Whole factory initialization, full boot, integrated display, and physical installation/recovery remained incomplete; product completion stayed 13/29, 44.8%.
