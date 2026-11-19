# CRYPTO Power and NVM Readiness Contract

Task `bw-0200`. The next request after OTP on, `DEVPWREN=0x08200400`, preserves OTP bit 27 and UART1 bit 10 while enabling CRYPTO bit 21. Compared CRYPTO bit 21 in SVD DEVPWREN/DEVPWRSTATUS, original enum 23, and stack address/mask.

All three original mains and the HAL fail CRYPTO enable if OTP status is off. Even after power status turns on, they wait up to 100 µs for bit 0 of `CRYPTO.NVMISIDLE` at `0x400c1f10`. On failure, they return through a common epilogue before requesting a clock. On success, they continue to the HFRC clock request path. The SVD reset value is 1, but it is not evidence that the current device is actually ready or that keys are loaded.

The SVD description of NVMISIDLE includes LCS validity and internal NVM operation/key-related processing. Providing a mock idle bit therefore differs from reproducing the lifecycle, keys, and crypto engine. The next model supplies only explicit active/stuck power and a separate idle/busy/unknown readiness flag. It blocks the register if power or OTP is not on, or readiness is unknown. Writes to that flag and other CRYPTO registers, OTP bytes, fuses, and security settings are unsupported.

The pinned HAL `61b293a49db34030c545f99101f7ebf6a3050314`, SVD/header, and three originals' requests, prerequisites, literals, wait arguments, error branches, subsequent clock BL, and caller without a check were verified in 31 checks by `tools/inspect_crypto_power_contract.py`. The result is outside Git at `simulator/crypto-power-contract-01/report.json`. This investigation did not change the model or native endpoint.

Follow-up verification covers preservation of default unknown, OTP prerequisites and shared-bank atomicity, power gating and read-only policy for the idle flag, busy/stuck faults, and the original natural execution path. Mock readiness does not imply actual cryptographic operations, physical power stability, whole boot, or display success. No physical device was accessed; product completion remained 13/29, 44.8%.

The later [power and NVM flag model](crypto-power-ready-model.md) performed seven native, 163 unit/regression, seven post-stop gate conditions, and 212 evidence checks. The next HOSTCCISIDLE and fault-path OTP PTMSTAT accesses remain blocked.
