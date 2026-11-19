# Same-board UART nonzero-length MRAM recovery

2026-11-17 · bw-0582. Original reset was connected through UART2 authentication, LOAD/RUN, original API3 stream, original stock 2.3 MRAM function, original readback/progress, RESULT, CONT/RLSD, and main entry. **Actual virtual corruption/restoration of 16 bytes** was confirmed in two cold sessions. Execution evidence for BV06 was obtained; overall judgment of all 12 conditions is performed in a separate final audit.

## Actual execution and model boundary

Upstream commit 42e27e9 recover payload, 264 bytes with SHA `f046754b…408732`, is placed in SRAM through original UART reception. Host does not directly set guest code, PC, or IRQ. Approved-image byte/range policy is the same as previous checksum and explicitly registers only this image.

Target is 16 bytes at main `0x438010..0x438020`. Corresponding stock bytes are all 0; each was changed to A5 in a private fixture before starting. Full initial main SHA is `f5651368…aabbb0`; restored SHA is original `69f9ef63…13b9c`. Restoration success was not inferred from length 0 or rewriting identical data. Scope of this 16-byte test is not expanded to damaged vectors/executable code or full firmware restoration. Full main/full-stock restoration has separate existing evidence.

Original recover ARM receives 16 bytes through API3 recv and calls stock 2.3 MRAM function `0x42e83d`. At ROM entry `0x0200ff20` actually requested by that function, **an explicit functional model substitutes for original Boot ROM**. It checks key 12344321/op 1/word offset e004/count 4/PRIMASK 1/ROM power-ready/SRAM source/approved 16 bytes, then writes four words only to virtual main. ROM return R0/PC=LR handling is the functional-model boundary, not original ROM instruction execution. Boot/main execution policies and prohibition of direct guest MRAM writes remain.

Original code subsequently performs D-cache invalidate, four-word readback comparison, progress 16 transmission, ACK receive, and RESULT 0. The model additionally permits only invalidate of specified line 438000 after successful 16-byte writing. It does not allow all MRAM cache accesses or precisely reproduce physical cache. Existing MRAM control model was connected through shared-guard address ownership.

## Control results

| Run | Result |
| --- | --- |
| Two 16-byte corruption restorations | One ROM ABI call, 16 bytes programmed, readback/progress/RESULT 0, main, full main original SHA match |
| Stock 2.3 boot, same model/board | Recovery/UART input/ROM calls 0, main entered |
| ROM error 7, corrupt fixture | Program 0 bytes, RESULT 08000107, progress 0, CONT/RLSD, main; corrupt SHA retained |

Main-entry PC/SP/MSP/PSP/CONTROL/VTOR match across four cases. Full SRAM, instruction count, and physical latency identity are not claimed. Functional assumptions include synthetic B0/trim 1, DWT 10 MHz, PMIC known-running/read-hole mock, and IOM7 synchronous off response. Only cold sessions were verified, excluding warm reset and multiple payload replacement.

The initial expectation that ROM error 7 returned as wire 7 was incorrect. Stock ARM `42e830` ORR 08000000 and `42e834` ORRS 100 produce `08000107`. Actual bytes `44f0006454f48074` and 32 wire bytes were independently compared. Main entry after error itself is not restoration success. This test corrupts reserved 16 bytes, so executable vectors remained.

## Diagnostic history, verification, and cleanup

First original recovery stopped at unmapped ROM. Later missing model policy binding was a pre-guest error, and an attempt to register control twice on separate sysbus was rejected during board creation. Control was corrected to shared-owner dispatch as in existing pending verification. Unsupported control after ROM connection and host-stream error response expectation/input-stage errors were retained. From the final error diagnosis onward, mismatches record raw frames and safely pause instead of throwing, preserving results. These failures were not counted as successful runs.

Forty-one native C# contract checks extracted from integrated source covered ABI range/length/key/IRQ/source bounds/default deny, MRAM invalidate only on success callback, rejection of other cache operations, and incorrect control writes. Host stream 3, scope 2, and existing runner 4 unit tests passed. Independent **71-condition audit** and `/tmp` re-audit with saved source passed 71. Initial audit 01 had one failure from incorrect expected ORRS opcode; 02/03 corrected it by comparing actual opcode and Capstone interpretation. Raw failure remains.

Termination and container absence for 12 owned native jobs were confirmed. Thirty-six duplicate firmware files totaling **73,462,296 bytes** were cleaned up. Canonical inputs, hashes, source/model/runtime, manifests, actual wire/logs, diagnostics, and audits remain. No physical serial/BLE/OTA/flash access occurred.

Evidence: `private:simulator/same-board-mram-audit-bw582-02/{report,cleanup-summary}.json`, independent re-audit 03/report.json. Initial raw scope.recovery_verified=false was a conservative pre-completion value. Historical reports were not overwritten; final audit jointly judged actual corruption/change/transport/main. Current runner's nonzero_mram_recovery_verified is distinguished from readonly diagnostic and requires full pre/post-corruption hashes, ROM record, completed wire, and clean main entry.
