# Approved-image-only RAM execution and repeated power responses

2026-11-17 · bw-0581. Overall **11/12=91.7%**, BV06 incomplete. Via original UART2 LOAD/RUN, upstream checksum code actually executed in SRAM, returned a result, and entered main. Do not confuse this read-only diagnostic success with completion of nonzero-length MRAM recovery.

## Actual path confirmed

Original reset → HMAC/OKAY → LOAD/DATA/CRC/READY → original RAM call → checksum RESULT `0xa0fd4d3f` → CONT/RLSD → watchdog/IOM7 cleanup → main were connected on the same synthetic B0/trim 1 board. Checksum is upstream 48-byte code, SHA `4bbd4bfb…47fc4ac`, reading the first 4096 bytes of main. Host CRC expectation and complete RESULT frame/checksum were compared. A new run with identical input confirmed the same result and main entry.

| Final control | Result |
| --- | --- |
| Normal checksum twice | One SRAM approval, actual execution, exact RESULT, main entry |
| Incorrect payload CRC | BAD_CRC → RUN UNAVAILABLE → RLSD → main; approvals/executions 0 |
| Tampered code + valid CRC | Original sent READY; byte policy rejected before first instruction; approvals/executions 0 |
| Stock 2.3 boot control | Same peripheral/policy model, no input; main entered without recovery worker/code execution |

Pinned stock control boot is 149760 bytes SHA `22a2b98e…175cc4`; patch is existing `7010d103…e55a7e`. Original main for both is `69f9ef63…13b9c`. Normal checksum and stock main-entry PC/SP/MSP/PSP/CONTROL/VTOR observations match. Exact identity of all CPU state, full SRAM, ticks, or instruction counts is not claimed. Old session memory may be reused after main initialization, so live snapshots and actual wire responses determined results.

## SRAM execution policy

`BlackwallSramPayloadGate` retains an internal copy of approved image. At first SRAM execution block it checks identity of all 48 bytes and entry/range, then allows only that area. It rechecks each instruction word against actual RAM afterward, including the second word of 32-bit instructions. Other SRAM, out-of-range, and tampering are rejected. MRAM write permissions, original boot/main read ranges, and ITCM initialization checks remain.

Bind is host registration of approved image bytes before policy.Attach. It does not write code into guest RAM or move PC/IRQ/stack. Original UART receive/LOAD placed code in RAM. Default profile has no approved image and retains existing first-SRAM-instruction rejection. Support is limited to one approved image per cold session; it does not establish code-cache consistency across warm reset or multiple replacement images.

Twenty-six pure byte-gate native checks cover image copy, unregistered access, entry/range/ulong overflow, full mismatch, post-approval tampering, and reset. RED was missing type; after GREEN 25, address-overflow boundary was strengthened for final 26.

## IOM7 power response

Existing model's default lazy response remains. New `synchronousOffResponse=true` is allowed only with successful off profile 0 and is a **synchronous functional response** applying ReadStatus's successful transition and PoweredOff callback immediately to a quiescent off request. It does not reproduce actual power delay/analog behavior. The option was enabled only on IOM7 object. No extra host/guest status poll was inserted.

Twenty-four native checks covered default pending-off reactivation rejection, three cycles of explicit response, one callback, nonquiescent rejection, reset, and rejection of stuck-on/undecided-off combinations. IOM7/DWT cleanup was also confirmed during repeated watchdog feeds and main return in actual recovery sessions. Existing PMIC initial-running/ignored-byte mock and DWT 10 MHz assumptions match [previous results](dwt-auth-main-results.md).

## Completion flags and remaining work

Initial native record's `scope.recovery_verified=true` was assigned by the then-helper for LOAD/RUN diagnostic completion. Raw record was not changed; final audit distinguishes `ram_diagnostic_verified=true` and `nonzero_mram_recovery_verified=false`. Subsequent runner separates the two fields. This record alone does not claim integrated MRAM restoration success.

Next execute upstream `recover.c` nonzero-length virtual MRAM recovery via the same UART/original API3 callback path. First assess reuse of a small aligned 16-byte explicit corruption/restoration fixture and existing verified ROM/MRAM functional contract. Writer calls original stock 2.3 MRAM function `0x42e83d`. Existing separated writer/stock restoration evidence is not carried forward as same-board actual UART-command completion. MRAM cache invalidate, callback stream, and permission/failure scope also need verification.

## Audit and cleanup

Frozen audit of execution/policy/original controls passed **83 checks**, with 83 on `/tmp` rerun. Runner input/classification 4 and upstream 5 also passed. A Python string edit immediately before integration caused a function-header syntax error, detected and corrected before process execution; it was not counted as failed native. Stock boot size was verified as actual 149760 bytes and hash/vector rather than guessed.

Ten owned native jobs terminated and current container absence confirmed. Twenty duplicate firmware files totaling **40,803,512 bytes** were cleaned up. Originals, approved image, hashes, source, model, plans/logs, RED diagnostics, and audit remain; ephemeral runtime build/cache was removed with containers.

Evidence: `private:simulator/bounded-recovery-audit-bw581-02/{report,cleanup-summary}.json`. No physical glasses/serial/BLE/OTA/flash access occurred.
