# CRYPTO Power and NVM Ready Flag Model

Task `bw-0201`. Following the [original contract](crypto-power-ready-contract.md), CRYPTO power and the NVM ready flag were implemented as separate opt-ins. The cryptographic engine, keys, LCS calculations, and OTP contents were not implemented.

## Contract and defaults

The shared bank's `cryptoPower` defaults to null. When connected, it requires the OTP owner, mask=`0x200000`, and offProfile=-1. `cryptoNvmIdle` accepts only -1 (unknown), 0 (busy), or 1 (idle); a known flag requires a CRYPTO owner. CRYPTO activation requires buck active and OTP on. The existing rejection of reserved or simultaneous domain changes and preservation of other domains remain in effect.

A read at `0x400c1f10` is provided only when the main owner's CRYPTO and OTP are both on and the flag is known. The upper guard region also looks up the same owner through `gpuControlOwner`. A fixed flag is an explicit scenario; reset 1 is not evidence of current hardware readiness. The SVD declares read-write access for this register, but the current model rejects writes because their behavior is unsupported. Other CRYPTO registers and byte, key, fuse, and security operations are also unsupported.

The CLI option `--crypto-power-response active|stuck-off` requires an active OTP scenario. `--crypto-nvm-idle idle|busy` requires selected CRYPTO power. Each is unknown when omitted. Reset initializes the power owner and NVM read counter while preserving the immutable flag selection. Turning off an on state is not implemented. Cancellation of a stuck request does not guarantee actual power-down or cleanup.

## Natural original execution results

| Condition | NVM wait R0 | power caller R0 | Final state / next block |
| --- | --- | --- | --- |
| Stock 2.4 / idle | 0 | 0 | CRYPTO on, HOSTCCISIDLE read |
| Stock 2.3 / idle | 0 | 0 | Same |
| Faceclaw38 / idle | 0 | 0 | Same |
| Stock 2.4 / busy | 4 | 4 | CRYPTO on, HOSTCCISIDLE read |
| Stock 2.4 / power stuck | Not reached | 4 | request cancelled, OTP PTMSTAT read |
| Stock 2.4 / NVM unknown | Not reached | Not reached | NVMISIDLE read |
| Stock 2.4 / default unselected | Not reached | Not reached | Existing CRYPTO power request |

The three idle originals read the NVM flag once and both wait and power functions returned 0. The original HFRC request path was also passed before the power return. In the busy case, the flag was read 101 times and wait and caller returned 4. This shows the virtual flag's effect on original waiting and branching; it is not a measurement of actual timeout duration, power stability, or key readiness. The caller continues without checking the error. The busy case also reads the next unsupported engine state, so it is not considered a safe fallback.

In the stuck case, the caller returned 4 without reading NVM, then cancelled the request. The final request/status is 0 and the phase is cancelled. Execution then stopped at OTP PTMSTAT `0x40014ac4` read. The first evidence check incorrectly expected the final state to remain stuck-off; it was corrected to match the observed cancellation. Neither the peripheral nor the guest was changed. Cancellation is not interpreted as physical power-off or successful recovery.

The next idle/busy read is `0x400c0a7c`, named `HOSTCCISIDLE` in the SVD. Stock 2.4 PC=`0x560712`; stock 2.3/Faceclaw PC=`0x52f7fe`. The NVM unknown guard is `0x400c1f10`, and the default unselected guard is the existing power request `0x40021004=0x08200400`.

All main bytes match the pinned bundle originals, and execution began at main reset. PC, branches, return values, and delays were not forced. The previous synthetic identity/memory/power and logical SDR assumptions remain. OTP/NOR history and the existing 2597-observation prefix were preserved. Idle/busy add two distinct wait/caller observations for 2599, power stuck has 2598, and unknown/default have 2597. All have capacity 4096 and drop 0. The prefix comparison is a projection explicitly removing new CRYPTO labels and renumbering sequences; compact observations are not treated as a full instruction trace.

## Tests and independent OTP gate verification

Unit and regression tests cover 163 conditions: idle 30, busy 30, power stuck 28, NVM unknown 29, default 2, OTP 21, and MSPI shared power 23 regression. They check power gating, root owner lookup, flag stability, read-only policy, rejection of other registers and widths, atomicity, Reset, and invalid owner. Successful unit power requests use a local ready mock, distinct from normal native bank requests.

Following a review recommendation to test OTP rejection independently, seven additional conditions were added. After normal original execution stops at the first guard and outputs its result, the host resets only the OTP/CRYPTO owners without resuming the CPU. With buck active unchanged, the test checks whether OTP off alone causes shared bank activation to be rejected atomically. The host then turns OTP on and checks that the same bank accepts the CRYPTO request and returns its state. This **post-stop host fault injection** is not classified as an original firmware error path or a physical recovery result. Original reports, execution inputs, and runtime prefixes were also compared separately.

Evidence in `simulator/` outside Git:

- `crypto-power-unit-01`, `busy-unit-01`, `stuck-unit-01`, `nvm-unknown-unit-01`, `default-unit-01`, `otp-regression-01`, `mspi-regression-01`: the 163 conditions above. The common prefix is `crypto-power-`.
- `crypto-power-main-01/`: seven original conditions.
- `crypto-power-otp-gate-01/report.json`: seven post-stop host conditions.
- `crypto-power-cli-01/report.json`: three rejections for missing prerequisites.
- `crypto-power-verification-03/report.json`: final 212 checks. These compare current source/compiled model, original/derived hashes, unit/native logs and reports, observed addresses and prefixes, history, path differences for each flag, default preservation, and host proof inputs and original report. The previous 209 checks were preserved.

Red records a platform-load failure caused by missing new constructor arguments. Subsequent model unit and original execution passed. A read-only review by an agent inheriting the parent model found no Important/Critical defects, and its recommendation for independent OTP gate tests was incorporated. Astra was not used.

## Next steps and limitations

The next step is to investigate the `HOSTCCISIDLE` consumer, engine initialization order, and availability of reusable upstream models. Additional ready bits alone do not establish support for actual cryptographic operations, key/lifecycle, or factory data access. Unknown accesses remain blocked.

The subsequent [HOST idle/OTP read contract](crypto-host-idle-contract.md) confirmed that the current consumer checks readiness for OTP word reads. The actual window's bank and contents remain unknown.

There was no glasses scan, connection, RAM payload, OTP/fuse/security write, MRAM, OTA, or flash activity. Full factory initialization, whole boot, integrated display, and physical device installation/recovery remain incomplete; product fulfillment remains 13/29, 44.8%.
