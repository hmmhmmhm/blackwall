# Restart Boundary in the IOM6 Shared Power Domain

bw403. The power request blocking bw402 delayed reconnection was **IOM6**, not UART. Cause was confirmed by collecting additional post-stop state without changing model, original ARM, or execution path. Delayed reconnection remains unexecuted; overall 7/16 (43.8%), E14 partial, and API 3/6 remain.

## Actual stopped state

| Item | Observation |
| --- | --- |
| Actual DEVPWREN request aggregate | `0xE20` |
| Value original attempted to write | `0xEA0` |
| XOR | `0x80`, changing only IOM6 |
| IOM6 | request 0/status `0x80`/phase `off-requested`, off profile 0 |
| IOM4 in same HCPC domain | request/status `0x20`/phase `on` |
| Buck | `active` |
| UART | Proposed value and current request identical |

IOM6 had not completed power-off through a status read after an earlier off request. `BlackwallPeripheralPower.TryWrite()` allows enable only from `off` or successful `powered-off`, so it rejects this restart. Unsupported write address/PC remain `0x40021004`/`0x494d78`.

New capture's main, model, board, initial inputs, and ATT/close/final full SRAM are byte-exact against the bw402 delayed boundary. Existing five JSON values also match. Only a post-stop power-property exporter was appended after the full execution script. The terminated machine was not resumed, and PC, R0, TCB, SP, branches, or connection state were not changed during execution. Derived properties such as UART Quiescent were queried only after stop.

## Original and public HAL evidence

Power HAL/header/Apollo header three-file SHAs from pinned `hal_ambiq` commit `61b293a49db34030c545f99101f7ebf6a3050314` were checked. HAL groups IOM0–3 in HCPB and IOM4–7 in HCPC. If another enable remains in the same domain and its own enable is cleared, disable skips status polling.

Actual last-user helpers from original stock 2.4/2.3/Faceclaw were executed independently 48 times each, 144 ARM calls total. For each IOM, no enable, self, same-domain peer, both, other IOM domain, and UART were compared. Only with a same-domain peer enabled was last-user=false; DEVPWREN was the only address read and status reads were 0. Return to original caller stack was also checked. These isolated-function tests use explicit inputs and are not counted as full main executions.

Original IOM enum is module+3 and differs from public HAL enum. Actual masks/helper results were compared; public enum numbers are not copied into the original. Original disable's clear-store → last-user helper → skip status poll if false branch is the same common function previously confirmed during UART investigation.

## Scope of the next model

This is the same issue as the existing UART shared-domain gate contract, but the UART option is not applied to IOM. Next model the following lifecycle only in an explicit IOM shared-domain profile:

1. Distinguish local disable from domain shutdown when another same-domain port is actually modeled on and the target IOM is quiescent.
2. Handle local gate/reopen while the domain remains on. Do not force guest status polls.
3. When the last user turns off, consistently handle peripheral reset/completion events for gated ports too.
4. Reject or regression-check other domains, busy, undecided off responses, and default off.

Shared domain/skipped branch is supported by source and original functions. Exact register retention under local gate, physical power, and delay are not verified on real hardware. Functional-model assumptions must be explicit and checked with device-unit lifecycle tests and original delayed reconnection. Do not unconditionally allow all `off-requested` restarts or have the host initialize pending state.

## Verification and material

`probe_reconnect_power.py` collects only state after the original delayed run. `verify_reconnect_power.py` audits current aggregate/XOR, one-module change, identical full SRAM, existing reports, pinned sources, and 144 helper combinations in 15 checks. Report retains `scenario_passed=false` and `model_modified=false`.

The frozen tool's 15-check report is byte-exact. Three cases consistently tampering JSON/log/hash to change request delta, hide active same-domain peer, or hide helper status reads were rejected. Fourteen progress-management checks also passed. All 16 completion conditions and states remain; only next-work description was updated.

Private: `reconnect-power-native-01`, `reconnect-power-research-01`. One separate full main run and 144 isolated helper calls are distinguished. No actual glasses, Astra/subagents, or external publication occurred.
