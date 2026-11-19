# EDMP Frozen-Core Fault Experiment: Original Timeout Unverified

Follow-up bw422 ran further with a verified scoped observer and protection policy, identifying the [controller version query boundary](gaf-natural-timeout-controller-frontier.md) before the first timeout. It stopped at 11,059 of the 200,000-iteration limit and is not counted as timeout success.

bw397. A separate virtual fault component was added in which EDMP does not execute after a request and busy persists. Sixty-four device unit checks and identical check results from a frozen copy were confirmed. Actual stock 2.4 ARM main also reached request 2 and busy queries. **The original timeout return and subsequent app initialization were not confirmed.** Work is deferred and overall progress remains 7/16 (43.8%).

## Implementation and verification scope

New files are `tools/renode-gaf-frozen-core.cs` and `tools/probe_gaf_frozen_core.py`. Existing `renode-gaf-ondemand.cs`, `runtime_event_models.py`, and `run_runtime_connection_m55.py` are byte-exact against their earlier frozen copies. The generated model is also unchanged outside the IMU namespace. Automatic ready was not added to the normal default profile.

The fault component records requests 2/4, RMW, and pending and maintains busy. `CalculationSupported=false`, `CompletedCalculations=0`, and no calculation RAM is generated. This is an explicit virtual fault assumption, not verification of physical sensor failure behavior.

The original host setter's post-timeout mask/disable and calmag configuration transactions were also implemented under a separate RAM preservation contract. Writes are limited to addresses established in existing original traces. Four bytes at 0x5bc read state known from the preceding model's RAM clear and explicit host writes; they are not called calculation results. Writes outside scope are rejected before application.

This subsequent path was **verified only at device-unit level**. This main run remained in the first request 2 wait and did not execute the subsequent RAM path. Original branches, returns, TCB/SP, and timeout iteration count were unchanged.

## Actual stock ARM execution

| Item | Observation |
| --- | --- |
| Initial service completions | Existing 2, separate from new calculation completion count |
| GAF configuration | 41 fields, 153 bytes read, 225 bytes host writes |
| Request/trigger | Request 2, trigger 1, `a272:1f/2a:cb/73:e9` |
| Busy queries | 1,643 |
| Original timeout return | 0 observed rows, not reached |
| Stop cause | Host 120-second limit for dedicated resumed interval |
| Stop PC | `0x5821d4` |
| Errors/guards | CFSR/HFSR, memory policy violations, and guards all 0 |
| Calculation/subsequent RAM | Calculation 0, subsequent RAM reads/writes 0 |

The original path permits up to 200,000 queries. **The host execution limit is not a firmware timeout.** The separate semantic verdict remains `passed:false`, `natural_timeout_observed:false`. Successful process exit is not counted as functional success. An observer-off control was not run, so observer neutrality is unverified.

The first preliminary integration requested 29900 ms against the shared delay input's 1..1000 ms range and was rejected. That capture, with 0 fault requests, was excluded from timeout evidence. A later run resumed in a dedicated interval after normal ATT handling without delayed peer input. The current tool adds a gate preventing resumption if earlier guard/architecture errors occur and an exit 1 verdict when timeout is unobserved. Absence of earlier-stage errors in the saved later run was also checked.

## Device checks and freeze

The 64 unit checks cover prerequisites, requests 2/4 and cleanup RMW, long busy persistence, zero calculations, RAM neighbors/range/rejection atomicity, preserved four-byte reads and overread rejection, and reset. They used the actual Renode device class but did not execute ARM firmware.

The frozen report has **identical JSON values and check list but different raw bytes**, due to per-process top-level JSON key order. The initial failed byte-exact expectation and original report were preserved. The missing-type red was confirmed by Renode TypeManager's type-absent message; the history that the initial inspector expected a different ImportError string was retained.

## Next work

The sleep callback `0x4b2f9f` was traced from original RAM device structure `0x20075578 + 0xc`. The path is original sleep wrapper → `0x495e88` → ITCM `0x40`. A 5 µs request is not assumed to become one RTOS tick.

Board `PerformanceInMips:10` and the callback path were confirmed, but **the host bottleneck has not yet been profiled**. Next measure actual engine, memory protection hook, MMIO, and observation costs. Routing all main pages through I/O is an investigation candidate, not an established cause. This single run is not presented as physical-device FPS or general performance.

Do not blindly repeat the same fault run for longer. Preserve protection, original branches, returns, TCB/SP, and iteration count; performance changes must first pass the same permissions, padding, and cross-boundary negative checks.

Private evidence: `gaf-frozen-core-research-01/{plan.json,native-semantic-verdict.json,sleep-timeout-source-contract.json,component-isolation.json,manifest.json}`, `gaf-frozen-unit-01`, `gaf-frozen-unit-frozen-01`, `gaf-frozen-native-02/stock24/observed`. Preliminary failure is preserved in `gaf-frozen-native-01/stock24/observed`.

The bw396 count was also corrected. Of 28 identical paths, one is an example .tdktool, leaving 27 identical src files. The original tree/blob comparison is unchanged and the initial manifest is preserved.

All 16 acceptance/status/evidence items and API 3/6 remain. Normal GAF calculation, original timeout return, full app boot, and integrated display are incomplete. No physical access, Astra/subagents, or external publication occurred.
