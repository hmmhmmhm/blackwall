# CRYPTO and OTP Power-Off Contract

Task bw-0206. The conclusion is that **the original cleanup's next operations are CRYPTO off → OTP off, and the upper consumer ignores both return values**. At that point the model blocked the first CRYPTO-off write. This document provides source evidence for shutdown support, not an implementation or physical verification result.

## Evidence and scope

`tools/inspect_crypto_otp_power_off.py` disassembles hash-pinned stock 2.4.0.24, 2.3.0.24, and Faceclaw 38 main and compares them with prior `otp-serial-slots-main-01` execution inputs, reports, and stopped registers. It checked 51 items. Results are preserved outside Git at `simulator/crypto-otp-power-off-contract-02/report.json`. No new main execution occurred.

HAL uses the [pinned hal_ambiq source](https://github.com/zephyrproject-rtos/hal_ambiq/tree/61b293a49db34030c545f99101f7ebf6a3050314). SHA-256 and commit were compared with local `mspi1-source-research-01/sources.json`. Agreement between HAL and original is source evidence for the behavior, not a measurement of silicon behavior.

| Location | Stock 2.4 | Stock 2.3 / Faceclaw 38 |
| --- | --- | --- |
| Power-disable function | `0x494e96` | `0x488fae` |
| Currently blocked enable-mask clear store | `0x494f3e` | `0x489056` |
| Consumer CRYPTO-disable call | `0x4d1c52` | `0x4c42a2` |
| Consumer OTP-disable call | `0x4d1c58` | `0x4c42a8` |
| CRYPTO clock-release call | `0x494f74` | `0x48908c` |

## Original sequence and failure handling

1. Look up peripheral information and return success if the enable bit is already off.
2. For OTP (enum 29), return code 3 (IN_USE) if the low revision byte at `0x4002000c` is less than `0x22` and CRYPTO status bit 21 is on. Do not generalize this as the same hardware dependency for all revisions.
3. OTP waits up to 100,000 µs for `PTMSTAT(0x40014ac4).BUSY` to clear. On error it returns before clearing the enable bit. This is a **different call from the timeout-free busy loop** previously found in read readiness.
4. Defer tempco and clear only the selected enable mask inside a critical section.
5. If this is the domain's last enable, wait up to 5 µs for status to fall. On failure skip CRYPTO clock release.
6. The CRYPTO (enum 23) success path calls release of HFRC clock id 4/user 23. After common handling it returns a disable status code. This check does not verify the entire clock-manager implementation.

The current pause is at CRYPTO enum 23 attempting to write enable word `0x08200400` → `0x08000400`. Immediately after CRYPTO returns, the caller supplies OTP enum 29 and calls the next disable. It still does not check returned r0 afterwards; it checks slot-selection state r7. Thus a selected string is not evidence of successful power shutdown. The OTP call can be reached under CRYPTO stuck-on, but the actual follow-on path had not yet executed.

## Model application boundary

`BlackwallPeripheralPower` already supports off responses and reactivation for some peripherals, but OTP/CRYPTO owner configuration requires offProfile=-1 and does not allow shutdown writes. This analysis did not change that restriction.

A follow-up implementation should provide shutdown responses only to explicit idle-read experiment profiles, retaining the default unknown boundary. HAL CRYPTO disable itself has no HOST-idle prerequisite. If the model requires HOST/PTM observations, document them as **conditions narrowing the supported experiment**, not silicon requirements. A model permitting OTP only after CRYPTO-off is also narrower than all behavior on newer revisions.

Before shutdown/reactivation support, connect readiness-observation history to power generations. The current slot gate checks cumulative HOST/PTM read counts, so enabling off/on could reuse observations from an earlier generation. Required changes:

- Update a monotonically increasing generation on power-owner reset, new activation, shutdown request, and activation cancellation.
- Bind HOST observations to both OTP and CRYPTO generations; bind PTM observations to OTP generation.
- Require current-generation readiness observations for slot reads. Distinguish cumulative diagnostic read counts from valid observations.
- Test shutdown success, stuck-on, reactivation, reset, and connecting a different owner, then run all three original main inputs under equal conditions.

This policy prevents stale state in the emulator. It does not implement or verify physical power timing, OTP programming, crypto engine/DMA, actual device OTP contents, or hardware recovery.

## Status

Later bw-0208 implemented the [shutdown response model for the idle-read path](crypto-otp-power-off-model.md). The incomplete items below describe the end of this source-analysis task.

Only source-contract analysis of power shutdown was complete. CRYPTO/OTP shutdown model, full consumer return, full boot, and display output were incomplete. Overall product criteria remained 13/29 (44.8%). There was no device access or persistent write.
