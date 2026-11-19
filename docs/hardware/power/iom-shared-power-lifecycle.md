# Shared IOM Power Lifecycle and Delayed Reconnection

bw404. **Under an explicit shared-power profile, original stock 2.4 completed 1000 ms delayed disconnect → re-advertising → second connection.** A control using the same code with option off stopped at the existing IOM6 restart guard and matched previous full SRAM/report values. Overall 7/16 (43.8%), E14 partial, and API 3/6 remain.

## Model contract

Shared `renode-strict-mmio.cs` and default board are unchanged. `iom_shared_power_model.py` checks pinned power class SHA `5221ccf2…` and exact owner read/write branches to create an optional model. `BlackwallPeripheralPower.sharedIomGate` defaults false. This board sets true only for five declared IOM2/4/5/6/7 owners.

- IOM0–3 are HCPB; IOM4–7 are HCPC. An on state in another domain does not allow local gate/reopen.
- When another port in the same domain is on in request/status/phase, buck is active, and target IOM is quiescent/offProfile 0, disable transitions to `gated`. The port's virtual request/status values are 0 and no whole-domain shutdown/reset occurs.
- Enabling a gated port under the same conditions returns it to on. Host does not clear pending or insert guest status polls.
- When the last user's actual off response succeeds, gated ports in the same group also emit `PoweredOff`, resetting connected IOMs. If last off fails, gated ports are preserved.
- Default off, undecided off response, busy, and absent domain before restart retain existing rejection boundaries.

Shared domain and skipped status poll are supported by bw403 public HAL and 144 original helper calls. Exact register retention under local gate, electrical status-bit delivery, and physical power/delay were not verified. These are explicit functional-model assumptions.

## Device-unit checks

119 actual Renode model checks passed. Original firmware was not executed in these units; some ready/quiescent states are explicit unit inputs.

Tests cover eight IOM domain masks, rejection of busy/not-ready/no-domain resumption, local gate/reopen, a single event on last shutdown, and cold restart/reset. Undecided/failed off, invalid non-IOM masks, and default off were also controlled. In actual owner status path, after preserving IOM6 registers, IOM4's last shutdown delivered IOM6 reset/clock initialization; IOM2 on in another domain did not prevent it. When the last peer gave explicit failure, IOM6 remained gated.

A red for missing four-argument existing-class constructor was confirmed. The first preparation assumed six owners and was rejected before execution because actual declaration had five. After correction, 119 checks ran; failure material remains.

## Original main and control

Both runs used the same stock ARM main reset, inputs, protection, and initial memory. Original PC, R0, TCB, SP, branches, and connection flags were not set. Sensor fault profile retained request 2/trigger 1/busy 926, pending=true, calculations 0.

| Check | Profile on | Same model, profile off |
| --- | --- | --- |
| Full SRAM through ATT/disconnect | Byte-exact with previous material | Byte-exact |
| Re-advertising | Original parameters/enable, two explicit responses | Not executed |
| Second connection | GPIO/IRQ/H4 → original WSF → CCB reallocation → original return | Not executed |
| Next state | CCB active/state 3/handle `0x40`/role 1, IRQ/pending clear | Existing `40021004←EA0` guard 1 |
| Final existing SRAM/JSON | Preserved separately for new continuation | Previous final full SRAM and five JSON values exact |
| Fault/guard | CPU fault 0/guard 0 | CPU fault 0/existing guard 1 |

On-profile re-advertising took virtual 14.9523 ms; second-connection input to original opened-function return took 4.2467 ms. These are not physical BLE performance figures. GPIO edge 11, one second-connection IRQ, original task/stack return, and handle/peer address were confirmed. Final IOM6 is gated/request 0/status 0; IOM4 is on/request=status `0x20`. Actual device PowerDown and full power-cycle counts match for each port.

The previous verifier rejects model/board/runner changes. That false result was preserved; the new audit independently checks exact power transformation, selected option, and observation suffix. Existing 21 on checks and nine off-boundary checks remain except three configuration-related items. Eighteen separate configuration/lifecycle checks were added. Source/model identity standards were not lowered to pass.

Four cases consistently tampering JSON/log/input hash for missing reset, unselected owner, absent HCPC peer, and false sensor completion were rejected. Frozen tool audit reports are byte-exact. Fourteen progress-management checks also passed.

## Remaining scope

Normal GAF calculation, full app initialization, second ATT, reconnection for original 2.3/Faceclaw, and actual HCI response-loss timeout remain unverified. Controller reason `0x08` injection is not counted as actual local timeout expiry. E14 is not assessed complete. Next is actual response-loss/timeout contract and the same failure scenario on other originals.

Tools: `iom_shared_power_model.py`, `verify_iom_shared_power.py`, `probe_iom_shared_reconnect.py`, `verify_iom_shared_reconnect.py`. Private evidence is preserved in `iom-shared-power-unit-*`, `iom-shared-reconnect-native-01/{enabled,disabled}`, and `iom-shared-power-research-01`. Two original runs and separate device units are distinguished. No physical device, Astra/subagents, or external publication occurred.
