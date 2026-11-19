# CRYPTO and OTP Power-Off Response Model

Task bw-0208. Added shutdown responses for the idle OTP read path based on the [original shutdown contract](crypto-otp-power-off-contract.md) and [power generations for readiness observations](otp-readiness-power-generations.md). Stock 2.4, 2.3, and Faceclaw 38 main passed the previous CRYPTO shutdown block and returned 0 from both shutdown calls and the NVdb initializer. The next boundary was an MSPI configuration write. This was not a complete boot or physical-device validation.

## Supported scope

`BlackwallCryptoOtpPowerLifecycle` accepts only readiness explicitly specifying HOST idle=1 and PTM busy=0. Root and lifecycle must share the same readiness object, whose OTP and CRYPTO owners must also match the root. A power owner with an offProfile cannot be connected to the root without this lifecycle.

- CRYPTO shutdown requires both HOST and PTM observations in the current power generation.
- OTP shutdown requires a PTM observation in the current OTP generation, CRYPTO `powered-off`, and request/status 0.
- Power responses use the existing generic owner's `off-requested` → `powered-off` or `stuck-on` transitions. The next domain is not shut down before reading status.
- Reserved bits in the shared DEVPWREN bank, rejection of simultaneous changes to multiple domains, and atomicity remain enforced. Shutdown readiness queries do not change state.
- The default off response is unknown. Connecting the lifecycle does not activate an individual owner's unspecified offProfile=-1.

These conditions **limit the supported idle-read experiment**. The HAL's CRYPTO disable itself does not check HOST idle. The rule requiring OTP shutdown after CRYPTO-off does not describe actual behavior of every chip revision. The crypto engine, DMA, OTP programming, actual power states, and physical timing were not implemented.

Added `--crypto-off-response` and `--otp-off-response` to `probe_mspi1_power_off_main.py`. Each accepts `unknown` (default), `off`, or `stuck-on` and requires explicit selection of active power, HOST idle, PTM clear, and NVM idle. The default board configuration is unchanged. A shutdown response may be specified for only one domain; the other remains blocked.

## Original execution observations

Added only two observation points, immediately **after** the source-verified consumer's CRYPTO and OTP disable calls. No hook was added to the shared HAL epilogue. Existing main-reset entry, pinned main bytes, branches, and return values were unchanged. All runs below used synthetic blank KVdb/NVdb, a synthetic string, and explicit readiness states. No device identifiers or private backups were used.

Results outside Git: `simulator/crypto-otp-off-main-01/`.

| Run | CRYPTO / OTP return | Observation |
| --- | --- | --- |
| stock24 | 0 / 0 | Both powered off; NVdb initializer returned 0. PC `0x4e8a46` |
| stock23 | 0 / 0 | Same. PC `0x4db672` |
| cfw | 0 / 0 | Same. PC `0x4db672` |
| stock24-crypto-stuck | 4 / not reached | CRYPTO stuck-on. Caller attempts OTP shutdown, but the model blocks `0x40021004←0x400` |
| stock24-otp-stuck | 0 / 4 | OTP stuck-on. Caller ignores the error; NVdb initializer returns 0 and reaches the same next boundary as the normal run |
| stock24-default | Not reached / not reached | Lifecycle not connected. Previous CRYPTO shutdown boundary, board, and observations retained |
| stock24-otp-unknown | 0 / not reached | Only CRYPTO shuts down. OTP shutdown write blocked at the existing unknown boundary |

The next boundary in the three normal runs and OTP-stuck is **`0x40061000←0x00100461`**. The MSPI1 model at the time stopped because it did not allow this change. It should not simply be relaxed into an arbitrary storage register: first identify the call, bit meanings, and peripheral state.

Subsequent bw-0209 [read-contract analysis](post-nvdb-mspi-read-contract.md) established that this operation was not a configuration change but a CTRL 16-byte PIO read start, rejected because the LittleFS address `0x01400000` was outside the existing backing.

Normal runs had 2,699 observation events and zero drops. Their projection with only the new shutdown observation points removed matched all 2,665 earlier events as a prefix. The synthetic string snapshot selected by the original consumer was also preserved. PTM observations increased from 32 to 33 due to one additional idle check before shutdown. Each shutdown was requested once, and all readiness witnesses were subsequently invalid.

NOR program count remained 242, with 3,238 bytes for stock 2.4 and 3,234 for stock 2.3 and Faceclaw. Advancing to the new boundary increased MSPI off cycles from 874 to 904 and XIP restorations from 873 to 904. These are simulated execution counts, not physical performance or power measurements.

Because the higher-level initializer returned 0 even when OTP was stuck, **initialization success cannot establish successful power-off**. Record domain phase/status alongside each shutdown return. This experiment does not validate a physical fault or hardware recovery.

## Verification and review

The failure caused by the missing component was preserved in `crypto-otp-off-red-02/renode.log`. The first red01 was a hexadecimal-format mismatch in the test generator, not a meaningful model failure; corrected red02 confirmed the missing type.

`verify_crypto_otp_power_off.py` ran 66 shutdown checks: 23 normal, 7 default, 16 CRYPTO stuck, 18 OTP stuck, 1 different readiness, and 1 unconnected lifecycle. The last two were **expected platform rejections**, checking exact constructor rejection before CPU startup. Renode returned exit 133 for those exceptions; they were not classified as successful process runs.

Including existing serial 83, readiness 30, and CRYPTO power 30 regressions, 209 local and regression checks passed. Two prerequisite CLI invocations were rejected before creating output directories. `verify_crypto_otp_power_off_evidence.py` used 134 checks to compare saved logs/reports, current model bytes, pinned main/derived assets, the complete previous event prefix, selected output, individual returns, and the next boundary. Results are preserved in `crypto-otp-off-verification-03/report.json`. Python compilation also passed.

An existing review agent inheriting the parent model compared the bw0207 backup with current changes. It reported no Important or Critical findings and requested confirmation of foreign, unlinked, and native evidence; the tests above supplied that confirmation. Astra was not used.

## Overall state and next steps

The next task was to analyze the original function and HAL contract for the new MSPI configuration write, then determine whether it required a state transition and compare stock and Faceclaw under the same conditions. Overall product completion criteria remained 13/29 (44.8%). Full main boot, integrated display, and physical installation/recovery remained incomplete; no glasses access, persistent write, or external publication occurred.
