# MSPI1 Power Request Model

Original ARM main execution passed the MSPI1 power request. This is a virtual power-state response, not successful actual MSPI transfer, full boot, or display output.

## Sources and boundary

Used four MSPI/HAL power files and CMSIS `apollo510.h` from pinned public HAL `zephyrproject-rtos/hal_ambiq` commit `61b293a49db34030c545f99101f7ebf6a3050314`. Original SHA-256 and Git blobs are preserved privately in `simulator/mspi1-source-research-01/sources.json`. MSPI1 base is `0x40061000`, IRQ 21, and DEV power mask `0x8000`.

Current SDK peripheral enum numbers differ from the G2 original caller's numbers. Do not treat current SDK MSPI1 ordinal 15 and original module+`0x10` call argument 17 as the same ABI. The model uses actual ARM request `0x8400` and public bit masks: retain UART1 `0x400` and add MSPI1 `0x8000`.

MSPI1 is an optional owner in the existing GPU/ADC/UART/IOM shared power bank. The active profile responds on at the first status read, an explicit assumption rather than measured delay or physical rail behavior. Without profile selection the previous strict guard remains. Unknown bits and simultaneous changes to multiple domains are blocked before state changes. With no shutdown-readiness evidence, MSPI1 off success is not supplied. Bus registers also remain strict.

## Execution evidence

- `mspi1-power-unit-03`: 23 unit checks using local ready-input mock. Covered mask/owner, initialization prerequisites, atomic rejection, reset, cancellation, stuck-off, and blocking actual MSPI1 addresses. Distinguish this from original-main execution.
- `mspi1-power-main-01`: four cases—stock 2.4.0.24, stock 2.3.0.24, Faceclaw 38, and unselected control. Compared main bytes and pinned models. Stock 2.3/CFW used identical model/runtime conditions.
- Each of the three active inputs had one request/response, MSPI1 request/status `0x8000`, then stopped on a 32-bit read at `0x40004110`. PCs were 2.4 `0x4e7024`, 2.3/CFW `0x4d9c50`. Behavior at the new address requires follow-up investigation.
- The unselected control retained the prior `0x40021004` write `0x8400`, PC `0x494d78`, stop.
- `mspi1-power-shared-regression-01`: 14 existing UART/GPU/ADC shared-bank DRIVER checks passed on current core and fully pinned board. This was not a full lifecycle-extension regression.
- `mspi1-power-stuck-main-01`: in stock 2.4, a stuck-off condition with virtual power status 0 also reached the `0x40004110` read. The full error path was not executed; safe stopping/recovery was not established.
- `mspi1-power-verification-02`: rechecked 77 items including saved unit markers/reports, current driver/full model, public original SHA/blobs, original ARM, file hashes, strict suffix, board/runtime derivation, full control boundary, and failure conditions. Preservation gaps in initial audit 57 were strengthened after review.

Reproduction tools: `tools/verify_mspi1_power.py`, `tools/probe_mspi1_power_main.py`, and `tools/verify_mspi1_power_evidence.py`. Supply the private `simulator` path as first argument and a nonexistent result directory as second. Run native Docker tests sequentially.

## Corrections and unknowns

The initial public MSPI source path returned 404; the actual `hal/mcu` path was found in the pinned tree. Unit02 used guessed bus-guard address `0x40068000`, and an invalid-mask constructor failure was indistinguishable from another prerequisite failure. Unit03 corrected this to the public MSPI1 base and tested invalid mask under the same prerequisites as a valid constructor. Initial results were not deleted.

g2flash's panel diagnostic label is developer analysis. Its handle slot differs from this original runtime slot, so the current MSPI1 peer is not established as a display. A stack-return candidate is not a complete unwind proof either. Original ISR, app loop, full boot from ROM, integrated framebuffer, and physical recovery remain unverified. There was no hardware access or Astra invocation. Overall acceptance stayed 13/29, 44.8%.

Later bw162 compared original BL, NOR source/function literals, and configuration object for the XIP-request caller, producing strong code evidence for a NOR initialization path. Actual chip/content identification remains incomplete. See [XIP boundary investigation](mspi1-xip-contract.md).
