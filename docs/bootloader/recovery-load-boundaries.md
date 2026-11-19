# Same-board recovery LOAD and execution-protection boundaries

2026-11-17 · bw-0580. Overall **11/12=91.7%**, BV06 incomplete. This task uploaded the upstream checksum payload via actual UART2 LOAD/DATA and confirmed original CRC/READY. RAM payload has not yet executed, and return to main through this command path remains incomplete.

## Command verified

The existing build of upstream `src/examples/checksum.c` was reused. Its 48-byte SHA `4bbd4bfb…47fc4ac`, entry 0, and metadata are pinned. It is a nonpersistent diagnostic intended to read the first 4096 bytes of main `0x438000` and return CRC32 `0xa0fd4d3f`. There is no flash/MRAM write or device access.

- After authentication, LOAD 32 bytes and three DATA frames of 32 bytes were supplied through UART FIFO. Original responses were ACK×3→READY. Through RUN 32 bytes, 185 bytes total were consumed by the original. Independent frame/checksum/receive FNV64 were compared.
- First RUN stopped on DCCMVAU clean-to-PoU write at `PC 0x43503a`. Upstream ram_invoke.h uses `0xe000ef64`, absent from existing coherent cache.
- DCCMVAU was added within existing `sramAddressMaintenance` contract. Aligned SRAM line range, 32-bit width, and default-off rejection remain, with separate PoU clean counter. This is a synchronous coherent functional contract, not actual cache content, bus latency, or silicon accuracy.
- After correction the original cleaned two cache lines and invalidated I-cache. RUN stopped at payload's first instruction `0x2001c7a0` under existing `execute-outside-code` policy. That instruction has not executed and there is no RESULT response. SRAM executable scope was not widened and PC was not forced.

## Negative command and next power boundary

A control flipped one bit only in the payload CRC supplied to LOAD while retaining correct frame checksum. The original responded **BAD_CRC** to final DATA and **UNAVAILABLE** to subsequent RUN. Cache clean 0, RAM execution 0. It also actually received CONT 9 bytes and transmitted RLSD 13 bytes. However it then stopped before main at the IOM7 power boundary on a repeated watchdog call.

Actual guard: `PC 0x4349c6`, shared PWRCTRL `0x40021004`, proposed `0x0d00`. XOR with existing request `0x0c00` is **IOM7 bit 0x100**. IOM7 was `off-requested`, request 0/status 0x100. Original watchdog does not read status after the previous off request; it feeds during the held session, then feeds again after CONT release. The existing functional power model completes off only on ReadStatus and rejected reactivation.

This is not interpreted as UART failure or another peripheral's power write. No guest poll was inserted and no host status read forced a completed transition. Next preserve default contract while verifying off completion/reactivation independent of status read in an explicit response model. Actual power latency is not claimed known.

## Next execution policy

A separate policy must allow natural SRAM execution only for the verified 48-byte checksum by byte identity and range. Other SRAM, tampered code, and out-of-range execution remain rejected, with MRAM write protection retained. BV06 is not completed before checking original CALL/ABI/return and actual RESULT, error, and stock controls. LOAD/READY alone does not establish checksum execution or recovery completion.

## Verification, failure history, and cleanup

Cache native RED was `SRAM-clean-to-PoU` rejection; after correction **66 checks** passed, including width/range/default rejection and existing set/way behavior. Historical frozen cache lacked Reset method, causing first composition preflight failure. The two existing forms are distinguished and Reset counter extension applies only to models having that method; the failed preflight was not executed.

**40 audit checks** on three final natives (initial cache rejection, first SRAM instruction rejection, CRC negative/power boundary) and 40 `/tmp` rerun checks passed. Existing input/classification 4 and upstream runner 5 passed. First audit incorrectly expected no additional RLSD in negative case and was corrected to check the entire additional 13-byte checksum and 194 bytes consumed. Failed audit 01 remains.

Complete original boot/main hashes remained unchanged in all result-collection natives. Five owned natives terminated with current container absence, plus one preflight-only case confirmed. Fourteen duplicate firmware files totaling **28,576,436 bytes** were cleaned up. Canonical checksum/originals, hashes, source, model, logs, failure diagnostics, and audit remain; ephemeral runtime build/cache was removed with containers.

Evidence: `private:simulator/recovery-load-audit-bw580-03/{report,cleanup-summary}.json`. [Previous authentication/main completion](dwt-auth-main-results.md) remains, but is not carried forward as completed return to main for the new recovery command.
