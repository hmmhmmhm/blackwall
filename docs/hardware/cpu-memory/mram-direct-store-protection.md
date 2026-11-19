# Blocking Direct Stores to Virtual MRAM

2026-11-17 · bw-0563. This records a model defect found during BV09 review and evidence for its fix. There was no physical device access; this does not claim to reproduce actual silicon ROM permissions.

## Finding and revised assessment

The existing `SetHookAtMemoryAccess` was an observation hook. Executing a single STR from a synthetic SRAM Thumb caller at boot `410000` reported a violation, but four MRAM bytes had already changed. Tests rejecting invalid requests through the `Program` API did not cover this path.

The failed result at `private:simulator/direct-mram-store-bw563-01/report.json` is preserved. BV09 was reopened from done → partial and progress reduced from 5/12 → 4/12. After the fix and verification below passed, it was restored to done and 5/12 = 41.7%. The failed result was not overwritten with a pass.

## Actual write boundary

Changed MRAM in the isolated recovery fixture from `MappedMemory` to `BlackwallProtectedMram : ArrayMemory`. Execution with the pinned Renode 1.17 binary verified that executable IO code fetch and byte/halfword/word method overrides work. Instead of relying on CPU fast-path stores and an after-the-fact hook, each write method checks the armed state and returns before modification. The observation hook only records the block and stops execution.

Call `Arm()` after initial snapshot loading; there is no disarm operation. The explicit ROM model programs through a separate internal method after the existing key/operation/alignment/source/destination/IRQ checks pass. This is a virtual ROM contract, not physical MRAM security or electrical behavior. Other memory models across the whole board were not automatically changed.

## Verification results

- Synthetic M55 STR: four targets at boot `410000`, main vector `438000`, main body `438010`, and metadata `7fe000`.
- Synthetic M55 STRB/STRH: two cases targeting boot `410000`. All executed actual instructions.
- All six had one blocked write, one observed violation, zero ROM calls, and zero programmed bytes; the complete 4 MiB MRAM was byte-identical before and after. A fixed nonzero A5 pattern was used. Do not describe the synthetic caller as execution of stock firmware.
- Four cases passed with the existing compiled ARM context wrapper/RAM writer/callback/stock MRAM adapter: normal, ROM status 7, readback mismatch, and interruption after 68 words (272 bytes). Actual ARM fetches and executes boot code from executable IO. The original ROM function is modeled.
- Independently reconstructed the entire MRAM of the four regressions from baseline and payload and compared SHA and bytes. ARM UART frames, context restoration, vector preservation, and error/interruption results also matched the existing contract.
- Reverified 23 API policy conditions and eight actual Program rejections on the new memory model. These 31 are C# component tests and are not added to original ARM execution counts.
- Ten host restoration checker tests and six recovery runner tests also passed. The first runner import failed because Unicorn was absent from the default Python; six tests passed in the existing dedicated venv.

Evidence is in private simulator `direct-mram-store-bw563-02` through `07`, `protected-mram-atomic-bw563-01`, `protected-mram-replay-bw563-01/{normal,rom-failure,readback-mismatch,cut-68}`, and `audit-and-cleanup.json`. Model, runner, board, guest code, execution logs, and hashes are preserved.

After verification, removed 35,651,584 bytes of duplicate MRAM/SRAM/final regression dumps and temporary before/after 4 MiB direct-store dumps. The 512-byte regression body, baseline paths, full SHA values, and reconstruction evidence remain. Original logs, source, and results for the failure are also retained.

BV09 completion applies to the declared isolated virtual policy. Same-board UART2 authentication → recovery → main (BV05/06), full main restoration → natural reboot (BV10), and full-stock restoration of all modified persistent areas (BV11) remain incomplete.
