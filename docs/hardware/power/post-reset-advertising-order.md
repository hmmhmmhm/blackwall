# Reinitialization Advertising Command Order and Strict Responses

bw410. **Reinitialization advertising order was confirmed using complete original-generated payloads and explicitly supported only in subsequent reset generations.** A new stock 2.4 generation processed all pinned startup 59 commands/60 responses and five advertising transactions. It stopped at an existing normal-response observation point before credit restoration, so full app recovery and reconnection success remain unverified. Overall 7/16 (43.8%) and E14 partial remain.

## Complete buffer collection

Only original HCI sender `563c08` entry observation was added to the existing bw409 IOM6-stopped run. Original allocator-created opcode/length/payload buffers, caller LR/SP, task/Thread context, and reset generation were read. Firmware, model, board, and clock were unchanged and no response was added.

Existing eight JSON report values and four complete SRAM snapshots (ATT/close/timeout/final) matched bw409. This is a control for this input and collection state, not a guarantee that all CPU/peripheral state or other paths are unaffected. It is not generalized to raw JSON byte identity.

A total of 59 sender candidates were collected: two generation-0 re-advertising 2006/200a commands and 57 from generation 1. The first 52 generation-1 buffers matched existing pinned buffers from HCI Reset through AES; the last five also had identical payloads. Actual caller BL563c08 and each parameter length were verified.

| Transaction | First initialization order | Reinitialization order |
| --- | ---: | ---: |
| 2005 address | 1 | 1 |
| 2006 advertising parameters | 2 | 4 |
| 2008 advertising data | 3 | 2 |
| 2009 scan response | 4 | 3 |
| 200a enable | 5 | 5 |

The parameter command was generated later, not omitted. The complete higher-level cause of firmware state choosing this order has not been analyzed. The earlier suggestion that it was omitted because prior advertising configuration was retained is not established; this material shows actual later generation.

Sender candidate collection proves generation/calls. It does not mean all 57 were transmitted on the wire in the run blocked by the existing guard. Actual 59/60 transaction consumption was separately confirmed by the order-supporting run below. Generated buffers and response fixtures contain virtual address, name/manufacturer data, and AES test values, so they remain outside Git.

## Model changes and unit controls

Shared `renode-em9305-reset.cs` and existing generation/loss/reconnect extensions were preserved. New `post_reset_advertising_model.py` adds `postResetAdvertisingDataFirst`, default false. Enabling it requires an explicit reset generation; only for generation>0 does it select advertising indices 0/2/3/1/4. Initial generation and separate runtime re-advertising order are unchanged.

Five commands and corresponding replies are selected by the same indices. Payload, exact bytes, opcodes, lengths, chunks, response count, 59-command budget, reset limit, and guards remain. Arbitrary orders are not accepted and commands are not unconditionally ACKed.

Actual Renode units passed 2,863 assertions each for enabled/default order. Existing initial startup and reset were performed as actual peripheral transactions, and five collected original buffers compared as independent evidence of the new order. Every payload byte's valid acceptance/tamper rejection, exact reply, and rejection of additional startup were checked. Unit initial-startup priming uses existing fixtures and is distinct from original main execution.

## Original main integration result

From the same original main reset, execution passed ATT/time, 1000 ms delayed disconnect, completion loss, original timeout, reset pulse, and internal event 38 handling. The new option was explicitly enabled. The host did not write original PC, branches, registers, timers, or credit.

The peer verified 59 pinned commands sent by the original in order, and the guest consumed 60 responses. Advertising command/reply was 5/5, peer Complete/pending=false. Guard, CPU fault, and memory policy violations were 0. Previous-generation history and original message handling/task path were preserved.

After 263.292 ms resumed time, execution reached `563d32` while handling the normal response to advertising enable 200a. This is where existing `WatchHealthyStop` observer pauses after original timerStop returns. Timer active=0 and credit still 0. The next original store has not yet executed to determine whether it restores credit. This is therefore not described as virtual three-second idle verification.

The sensor remains in the explicit frozen-core fault/pending state with 0 calculations; this is not evidence of normal GAF, full app boot, or actual radio advertising. A new connection after reinitialization has not yet been injected. Next check credit and original state cleanup after the normal-response observation point, and handling of a new virtual connection.

## Audit and preservation

Five observation-baseline checks, 18 existing-boundary checks, and 22 new-enabled checks passed. Current/frozen tool reports are byte-identical. Three cases consistently tampering JSON/log/hash for full payload, generation order swap, and false completion counter were rejected. Fourteen progress-management checks also passed.

The initial audit changed the same start string in a later resumed interval too, creating an incorrect expected runner. It was corrected to compare only the actual runner's first observation point; original execution was not restarted. Failed verifier and exploration material were preserved. Individual acceptance conditions and states remain unchanged.

Tools: `probe_post_reset_advertising.py`, `renode-hci-emission-observer.cs`, `post_reset_advertising_model.py`, `verify_post_reset_advertising_model.py`, `verify_post_reset_advertising.py`. Private: `post-reset-advertising-research-01`, `post-reset-advertising-native-01/02`, `post-reset-advertising-unit-01`, `post-reset-advertising-unit-off-01`. No physical access, Astra/subagents, or external publication occurred.
