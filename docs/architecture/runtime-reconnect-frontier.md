# Re-Advertising Request After Disconnect

bw401. Execution continued after original ARM connection-close handling to identify the next controller request needed for reconnection. Successful reconnection remains unverified; E14 remains partial, overall progress 7/16 (43.8%) and API 3/6.

## Original execution boundary

After running stock 2.4 from main reset through existing ATT time setting and immediate disconnect, natural execution continued from original close return address `0x4d4044`. Separate observation limits of 500 virtual ms and 45 host seconds were set, but execution stopped earlier at an unsupported GPIO read. The aborted machine was not resumed.

Main, model, board, initial inputs, and complete ATT/close SRAM are byte-exact to prior bw400. Three JSON reports have equal values but different raw key order. The execution script appends only an observation segment after the entire previous script. PC, R0, TCB, SP, original branches, and connection flags were not set.

| Item | Actual observation |
| --- | --- |
| Virtual elapsed after close | 8.5809 ms |
| Stop PC | `0x501676`: `ldr r0, [r0]` |
| Rejected read | GPIO117 RDY word `0x40010410` |
| Prepared HCI packet | `0106200fa000a0000001000000000000000700` |
| Packet length/opcode | 19 bytes / `0x2006`, LE Set Advertising Parameters |
| Original packet location | Extracted from actual R10 buffer and R8 length |
| Existing initialization commands/responses | 59/60, no increase |
| Connection-related inputs consumed | 4, pending=false |
| CCB | All three slots remain inactive/state 0 |

The packet is byte-exact to the board-pinned first advertising-initialization parameter command. The existing peer permits no additional transmission after its 59 initialization commands. It did not transition to a new write state on CS low, so the RDY query reached the strict guard. This packet had not yet been sent over SPI; do not count it as advertising restart, controller response, RF behavior, or actual successful reconnection. Guard 1 is an unsupported simulator boundary, not explicit original failure handling.

This run selected the frozen-core profile but stopped before a sensor request (request 0). Calculation success remains 0; do not extend this to observation of re-advertising during actual busy state.

## Source-supported reconnection path

Hashes of six files in pinned Cordio source commit `54e8693ef4ff7e025018094f290a1d5cf380941f` were rechecked. A peripheral successful connection event allocates a new CCB when none exists at the existing address, and an idle connection-complete message transitions to connected/accepted. This is comparable public source, not a claim to have reconstructed G2's exact source.

The actual state tables of all three originals have idle/message 4 → state 3/action `0x22`. Disassembly confirmed that the action set 2/index 2 wrapper calls the existing original opened-handler function. Initial assumptions of action 6 and that the wrapper itself was the opened function each failed assertions. Actual table, RAM action pointer, and wrapper call were compared without confusing numeric values with public-source names. This is a source-supported path, not evidence of executing a second connection.

## Verification and next implementation

`tools/verify_runtime_reconnect_frontier.py` checks saved capture hashes, logs, full SRAM, original instruction buffer, RDY instruction, initialization fixture, CCB, and strict boundary. The previous close audit and 14 new checks are distinguished. Saved audits do not run the current builder or rerun firmware.

Of two new native runs, the first failed export because of character conversion of post-close UART bytes. It was excluded from success evidence and its log retained. The next run preserved UART as hexadecimal and saved the stopped state without changing the original model or execution.

The 14-check saved audit and frozen-tool report were byte-exact. Two semantic mutations, consistently changing prepared packet or concealing the guard across SRAM/JSON/log/hash, were rejected. Fourteen progress-management checks also passed.

Next is an explicit opt-in re-advertising contract. Supply limited controller responses only when exact original requested commands, lengths, and order are verified, and allow a second connection event only after advertising-enable completion. Actual order of additional parameters, advertising data, scan response, and enable must be checked in later execution. Observation of the first command alone does not verify the whole four-command sequence. Preserve the default peer and existing evidence; arbitrary ACKs, counter resets, and connection-flag injection are prohibited.

Private evidence: `runtime-reconnect-frontier-native-{01,02}` and `runtime-reconnect-research-01`. No physical access, Astra/subagent, or external publication occurred.
