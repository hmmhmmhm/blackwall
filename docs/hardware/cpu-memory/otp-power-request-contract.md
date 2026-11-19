# OTP Power Request Contract

Task `bw-0198`. Compared the `0x40021004 = 0x08000400` write following [RX streaming](mspi1-array-rx-stream.md) with three pinned original mains, existing native stack, SVD, and HAL. This investigation did not change peripheral models, backing, or the original execution endpoint.

Confirmed SVD PWRCTRL DEVPWREN+4 `PWRENOTP[27]` and DEVPWRSTATUS+8 `PWRSTOTP[27]`. The concurrently requested `0x400` is UART1 bit 10. Previous MSPI1 bit 15 is off and must not be confused with the OTP request. SVD reset enable `0x08200000` was not injected unchanged into current execution state.

| Input | Power-enable function | Request store |
| --- | --- | --- |
| Stock 2.4 | `0x494ca0` | `0x494d78` |
| Stock 2.3 / Faceclaw 38 | `0x488db8` | `0x488e90` |

The original reads DEVPWREN, ORs the selected mask, then writes it. Stack request/status addresses are `0x40021004`/`0x40021008`, with mask `0x08000000` for both. The peripheral enum argument is 29. After waiting for status, if it is OTP the original calls a 100 µs delay function and checks status again. This is a static source contract, not a physical measurement of power stabilization time.

Public HAL `am_hal_pwrctrl.c` at `61b293a49db34030c545f99101f7ebf6a3050314` also contains an OTP enable/status table and an OTP-specific 100 µs delay. SVD/header and HAL source hashes were checked. The exact complete build linked into G2 was not identified.

The current caller does not check the OTP-enable return value and immediately calls enable for peripheral 23 (CRYPTO). Therefore observing a subsequent request under OTP stuck-off does not establish safe fallback. Public HAL also checks that OTP is on before CRYPTO power. Do not simultaneously allow OTP and CRYPTO as one model.

Next connect an optional OTP power owner to the shared bank with mock responses. Default unattached remains blocked. Explicitly select active/stuck-off and reject other-peripheral bit changes, simultaneous changes, and reserved bits. Do not automatically support OTP off, which separately requires a PTM busy check. OTP bytes, factory calibration, fuse writes, security settings, and the crypto engine are outside this power-response scope.

The later [shared OTP power model](otp-shared-power-model.md) executed active/stuck/unknown and five original conditions. CRYPTO requests after OTP on and PTMSTAT after stuck remain blocked at that stage.

Passed 31 checks in `tools/inspect_otp_power_contract.py`; results are outside Git in `simulator/otp-power-contract-01/report.json`. Compared original main/derived hashes, native logs/reports, read-OR-write, stack, UART1 preservation, delay branch, caller, and single guard. No model or device access occurred. Whole boot, display, and physical recovery remained incomplete; product completion stayed 13/29, 44.8%.
