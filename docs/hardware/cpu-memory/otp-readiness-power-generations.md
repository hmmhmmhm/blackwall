# Power Generations for OTP Readiness Observations

Task bw-0207. Fixed a prerequisite issue identified in the [shutdown contract analysis](crypto-otp-power-off-contract.md). It blocks a path where cumulative HOST/PTM read counts alone allowed synthetic-slot reads after power reset and reactivation. The CRYPTO/OTP shutdown model itself was not part of this change.

## Change

`BlackwallPeripheralPower.Generation` increments on reset at construction and subsequent resets, accepted activation requests, shutdown requests, and activation cancellation. Rejected requests and status responses do not increment it. Existing Request/Response/PowerCycles counter behavior remains.

A HOST observation stores both OTP and CRYPTO generations; a PTM observation stores only the OTP generation. The readiness object independently exposes whether each observation belongs to the current power generation. Synthetic-slot reads require these current-generation observations in addition to existing on/idle/busy conditions. Cumulative diagnostic counters are not cleared on ordinary off/on. Readiness reset invalidates all observations.

Thus, reactivating only CRYPTO requires a new HOST observation, while a PTM observation for continuously powered OTP remains valid. Reactivating OTP requires both new HOST and PTM observations. Once a shutdown request is accepted, the old HOST observation cannot allow slot reads even while waiting for a response or in stuck-on state.

This is a stale-state prevention contract for a synthetic readiness model, not a measurement of actual chip HOST/PTM bit changes, crypto engine/DMA, or power timing. Default unknown/unattached boundaries, the 128-byte range, and read-only policy remain.

## Verification

Preserved the pre-change failure in `otp-generation-red-01/renode.log`. After CRYPTO reset and reactivation it reproduced `old-HOST-witness-invalid-after-crypto-reset accepted`.

| Check | Count | Result outside Git under simulator |
| --- | ---: | --- |
| mock-first, reset/off/stuck-on/reactivation, rejection atomicity | 83 | `otp-generation-green-03` |
| Same contract for mock-last | 83 | `otp-generation-last-02` |
| Default slots unattached | 6 | `otp-generation-default-02` |
| HOST busy rejection | 6 | `otp-generation-busy-02` |
| Existing readiness regression | 30 | `otp-generation-readiness-regression-01` |
| Existing CRYPTO power regression | 30 | `otp-generation-crypto-regression-01` |

Total: 238 checks. Shutdown-success/stuck-on tests using local objects are not evidence of original ARM execution of shutdown. Root's OTP/CRYPTO offProfile=-1 restriction remains.

Sequentially reran three original ARM main inputs from main reset with the modified core. No forced PC, skipped branch, or substituted return value was added. Results are preserved in `otp-generation-main-01/{stock24,stock23,cfw}`. `tools/verify_otp_generation_evidence.py` audited 100 items including:

- Pinned main bytes, derived asset hashes, and agreement between current and saved models for each run.
- Matching complete stop state and selected observation events against prior `otp-serial-slots-main-01`.
- Matching all observation markers, HOST/PTM and slot markers, and NOR read/program/erase results.
- Retention of boot/display/hardware unverified indicators.

All three inputs read 32 words, selected candidate `P100MOCK000002`, and stopped at the same unsupported CRYPTO shutdown write as before. PCs were stock 2.4 `0x494f3e`, stock 2.3/Faceclaw `0x489056`. Shutdown and reactivation behavior had not yet executed in integrated main.

An existing reviewer inheriting the parent model compared the prior core backup in read-only review. No Important/Critical findings were reported; its suggestion to include generation in common rejection checks was incorporated. Astra was not used. Python compilation also passed.

## Next work and overall status

Later bw-0208 connected the [shutdown response model](crypto-otp-power-off-model.md) and confirmed progress after cleanup in three originals. The following is the next step as of the end of bw-0207.

Connect CRYPTO/OTP shutdown responses to an explicit idle-read profile and compare normal, stuck-on, and unsupported conditions. Guarantee shutdown order and owner identity while retaining default unknown. Then check original consumer return and the next unimplemented access.

Overall product acceptance was 13/29 (44.8%). Full boot, integrated display, and physical installation/recovery remained incomplete; there was no glasses access or persistent write.
