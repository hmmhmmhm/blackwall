# Timeout return and internal reinitialization notification handling

bw409. **The original timeout callback's return instruction actually executed, and the subsequent event 38 message was handled by the original WSF handler before the free function returned.** The new generation progressed through 55 initial commands and 56 responses, but stopped at a guard because subsequent advertising command order differed from the pinned model. Recovery and E14 are not deemed complete; overall 7/16 (43.8%) remains.

## Control before return

The same stock 2.4 main, model, board, frozen sensor, connection/time/delayed release, response loss, and reset generation 1 from bw408 were used. Model, original, branches, registers, and clock were unchanged. Only observations of message allocation/send, handler entry/return, dispatcher/free, and timeout-return PC were added.

At the existing pause before return instruction 563d24, six existing JSON report values and three complete ATT/close/timeout SRAM snapshots matched bw408. This includes existing R0–R15, time, task/stack, and guard. It controls the additional observer for this input and collected state; it does not guarantee no effect on all special registers, peripherals, or paths. JSON value comparison is not described as raw-byte identity.

The original instruction was naturally resumed without changing CPU PC. Existing guards remained, with subsequent virtual 3-second/host 45-second limits. In fact IOM6 guard stopped execution 245.8408 ms after resumption.

## Actual message path

| Stage | Original PC | Confirmed behavior |
| --- | --- | --- |
| 1 | 4dab72 | Message 20052e10 returned by original allocator |
| 2 | 4dab7e | Original send called with handler ID 1, same pointer, event byte 38 |
| 3 | 5647e2 | Original caller PC, restored SP, and saved register values after timeout pop |
| 4 | 4fa0f0 | Handler 1 entry receiving same pointer |
| 5 | 4fa10c | Indirect call to group 7 dispatch 4da999 in original table |
| 6 | 4da9a6 | Indirect call to event subindex 0 leaf 4da8f9 |
| 7 | 4fa110 | Handler return instruction reached |
| 8 | 4d7aec | Return to original dispatcher and SP after executing that instruction |
| 9 | 4d7af2 | Return after original free call on the same message |

All observations were in the original WSF task and Thread context. Other uninitialized header bytes immediately after allocation were not interpreted as normal status/parameters. Event byte and pointer identity were checked.

This is **internal reinitialization notification handling**. The official name of `event38` and an app error display were not confirmed. The source leaf sets an internal initialization flag and iterates 21 module initialization callbacks before proceeding to HCI reset, but all 21 actual calls were not individually traced. Thus previously unverified “app error notification consumption” is not equated with this internal message handling.

## Next boundary in new initialization

The new controller generation accepted actual original HCI Reset `01030c00`. It progressed through 55 startup commands and 56 responses validated by the pinned peer (including asynchronous P256 response), and one advertising initialization command/response. Runtime events remain 0.

Model initial advertising order is 2005→2006→2008→2009→200a. The first payload chunk the original next attempted during reinitialization was `010820201c02010618`, an opcode 2008 advertising-data command. The model slot then expected opcode 2006 advertising-parameter command `0106200f…`.

Original PC 582660 `str.w r2,[r3,#10c]`, r2=20200801, the nine-byte chunk in original SRAM, and address 4005610c were compared. The model stopped this mismatch with one existing IOM6 guard. CPU fault/memory-policy violations were 0 and GAF remains frozen/pending, calculation 0. **The complete advertising payload and subsequent command order have not yet been collected.** The temporary buffer following the visible chunk is not interpreted as the complete payload.

Do not conceal the difference with ACK or unconditional replay permission. Next analyze original advertising state, command selection, and actual payload after reinitialization, then add an explicit peer contract suited to that state. Retained host advertising configuration may explain it, but that remains a hypothesis. Full controller startup, new connection, and app-level recovery remain incomplete.

## Verification

Twenty-two audit checks confirmed original source bytes, pre-return equivalence, actual pop, pointer/dispatch/task/stack, free return, 55/56 initialization, and opcode-mismatch guard. Pinned and current tool reports are byte-identical. Three cases consistently tampering with restored SP, handler pointer, and mismatched opcode across JSON/log/hash and, where needed, SRAM/registers were rejected. Fourteen progress-management checks passed.

The initial audit incorrectly recorded LR for a 16-bit BLX as callsite|1. Only the expected value was corrected to actual next PC|1, 4d7aed; the original was not rerun. The failed verifier was retained.

Tools: `probe_controller_notification.py`, `renode-controller-notification-observer.cs`, `verify_controller_notification.py`. Private: `controller-notification-native-01`, `controller-notification-research-01`. No physical device, Astra/subagent, or external publication.
