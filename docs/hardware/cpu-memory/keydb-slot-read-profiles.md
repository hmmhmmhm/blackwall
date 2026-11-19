# Slot-Read Profiles for a Virtual Key DB

Task bw-0279. Connected the [original key DB contract](mram-keydb-source-contract.md) to explicit read-only fixtures. Default unknown remains blocked. `zero` and `uninit-ff` are synthetic virtual-device states, not actual pairing keys or original device dumps. Writable MRAM and physical device access were not implemented or executed.

## Model and default boundary

`BlackwallKeyDbSlotStorage` owns the same `0x7f8000–0x7fffff` range as the existing strict tail guard. However, under two declared profiles it supplies only the original slot scanner's byte loads. Supported addresses are ten slots starting at `0x7ff000` with stride 256; adjacent tail remains rejected.

It distinguishes each slot's first byte → remaining 255 bytes in order → caller's recheck of the first byte. Original consumer PC, R0/R4/R7, current slot, and offset must all match. Wrong address/order, repetition, another caller, host context, widths other than byte, and all writes go to the strict guard. Counter budgets are not arbitrarily increased and unknown data is not generated. Explicit reset clears fixture-check state but is not a persistent storage model.

Peripheral API unit tests supply explicit context to `TrySample`. The native path reads the actual current CPU and registers to apply the contract. Do not equate unit-test context inputs with natural ARM execution.

## Two original main paths

### zero

Stock 2.4, 2.3, and Faceclaw 38 each executed from actual reset main and completed ten slots and 2,570 byte reads. In the next stage the original tried to copy a 200-byte slot record and stopped on the first four-byte read at `0x7ff000`. This word consumer was not allowed by the current model. This is not full key DB loading, pairing, or completed main boot.

Copy uses original helper `0x439be4`; the next `LDM.W` instruction is four bytes starting at `0x439c0a`. The Renode stop report's PC was the inner halfword `0x439c0c`. The first stock 2.4 capture failed only PC prediction and passed the remaining semantic checks. Original capture/plan/report were preserved and a separate audit using `keydb-slot-zero-reviewed-candidate.json` confirmed this boundary. The same execution was not restarted and no branch was changed to match expectations. Do not generalize this observation into a PC rule for all 32-bit loads.

### uninit-ff

On stock 2.4, after the first slot's 257-byte check, original code entered cache-control preparation for the MRAM write wrapper. The existing MMIO guard blocked `0x40021014 ← 0x3f` at `0x494ada`.

Compared the following in actual registers/SRAM at that point:

- R5 is the original zero scratch buffer, with 256 bytes of zero.
- Applying the word offset in R6 to MRAM base `0x400000` gives destination `0x7ff000`.
- R7 is 32 words, preparing the first 128-byte transfer.
- The cache helper's saved stack has generic program constant `0x12344321` and the original MRAM wrapper return address.

The actual MRAM program callee had not executed. Full 256-byte recovery, the second half, and error/interruption recovery remained incomplete. Source contains a heal string, but that diagnostic log was not visible in this native UART run. Branch evidence therefore comes from read counts, actual context, subsequent calls, and SRAM; UART log generation is not guaranteed.

## Verification scope

RED failed because the new peripheral type was absent. The final 119 unit conditions cover slot order/completion for both profiles, invalid input, range, width, host access, rejection of all writes, reset, and invalid constructor settings. These peripheral API tests are independent of actual main captures. Existing BLE/IOM models were unchanged.

Final checks of subsequent native/audits, saved analysis, and provenance pins are recorded below. Default unknown and feature off are compared with the original strict boundary. Proprietary main/SRAM and execution artifacts remain in a private simulator outside Git.

## Remaining behavior units

Analyze and connect the original's next 200-byte record copy, empty-record handling and DB initialization, and cache/MRAM transactions for uninitialized recovery separately. Do not claim both are complete with only zero working. Before implementing MRAM write-ready, completion, and failure, verify the original service and per-version call contracts. Do not connect virtual storage to physical transport.

Separate erase/program of the EM9305 information area, independent recovery, and physical device version combinations also remain incomplete. Product completion stays 13/29 = 44.8%. Integrated main and 576×288 display success have not been achieved.

## Final checks

| Profile/input | Original path | Next block |
| --- | --- | --- |
| zero, stock 2.4/2.3/Faceclaw 38 | Ten slots, 2,570 byte loads | First word of 200-byte record copy |
| uninit-ff, stock 2.4 | First slot, 257 byte loads, then zero-write preparation | Cache-control write `40021014/3f` |
| unknown, stock 2.4 | New model supplied zero data | Original first-byte strict boundary |
| feature off, stock 2.4 | Original model retained | Original first-byte strict boundary |

- Six native runs and six saved audits. Raw zero stock 2.4 report retained execution success/PC-expectation failure; the other five passed their initial semantic contracts. All six separate audits passed. Native execution was not repeated to erase the failure.
- Unknown and off exactly matched existing-source CPU, instruction count, events, and stop boundary. Saved analysis compared the original zero-path 200-byte copy caller/LR/arguments and uninit MRAM word offset, zero source, 32 words, and stack program constant/return address. Reused 99 source zero-buffer initialization conditions after rechecking pins.
- Final component 119 conditions; regenerated six saved analyses with 21 pinned analyzer dependencies and confirmed identical reports. New model/execution/unit/audit/failed-PC review are pinned in private `keydb-slot-verification-01/manifest.json`. Existing BLE/IOM model hashes match.
- Preserve the boundary between original source and mocks. The model continues to reject consumers other than the slot scanner and all MRAM writes. Current results do not establish key DB record loading, completed automatic recovery writes, or preservation of actual pairing.

Follow-up candidates are `tools/keydb-slot-{zero,zero-peers,zero-reviewed,uninit,unknown}-candidate.json`. `zero-reviewed` is a separate audit contract for the first saved stock 2.4 run, not a replacement for the original execution plan.
