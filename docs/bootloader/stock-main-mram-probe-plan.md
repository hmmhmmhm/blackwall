# Stock main MRAM write-unit verification plan

2026-11-17 · bw-0569 · A staged diagnostic of the BV11 candidate path. Overall remains 7/12; this does not substitute for natural OTA, full-stock, or physical restoration.

- [x] Pin existing actual main/SRAM snapshot SHAs and original callback/ROM table. Confirm Python entry/fault input checks RED→GREEN.
- [x] A synthetic SRAM caller invokes the original main adapter, then original memcmp. The 4 KB target is 434000..435000 and includes an existing boot callback, but execution remains in main. Initial Thread/MSP/PRIMASK 0, existing callback pointer, and ROM-auto flag are preserved.
- [x] Execute original alignment/IRQ/power code and use verified MemoryStartup ready/stuck contract. Only ROM program is replaced with a fixed 4096-byte ABI/range functional model. This does not reproduce actual ROM bytes or electrical MRAM/I-cache.
- [x] Check ROM status 7, one-bit readback error, alignment error, and ROM power not ready. Compare actual returns and data to determine whether upper buffer/callback hides ROM errors.
- [x] If an unsupported boundary such as callback device-info getter appears, do not modify original snapshot to bypass it. Check and connect existing source-supported peripheral contracts or explicitly state the boundary.
- [x] Independently verify full 4 MiB MRAM before/after, source payload, neighboring boot/main/metadata, callback preservation, faults, IRQ restoration, and call traces. After completion clean build/cache/duplicate dumps while preserving source/log/hash and unique audit inputs.

This probe does not start in active RTOS/natural boot. Original functions execute in an isolated diagnostic Thread with original main and previous native SRAM loaded. Source callbacks are not erased and power helpers are not changed to success returns. The synthetic caller does not reimplement firmware copy algorithms; it calls only original write/compare. Original branches remain except for end observation and ROM ABI model.

Result: [original ARM execution, unsupported boundary, audit and cleanup](stock-main-mram-probe-results.md). Callback remains incomplete; the corresponding item means boundary identification and preservation are complete.
