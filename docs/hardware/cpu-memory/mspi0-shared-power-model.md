# Optional MSPI0 Power Response and Clock Boundary

bw-0304. Connected the [original power contract](mspi0-power-contract.md) to the shared power bank. No actual device was accessed and original main bytes, PC, and branches were unchanged.

## Implementation scope

Added `mspi0Power` as the startup fixture's final optional argument. Mask is `0x4000`; an existing ADC/GPU bank is required and the off profile must be unsupported. When omitted, bit-14 requests remain blocked as before. Active/stuck-off use explicit virtual responses from existing `BlackwallPeripheralPower`, not physical rail delay or measurements.

Merged the MSPI0 word into shared enable/status while retaining the existing contract that at most one owner changes at once. Reserved bits, simultaneous changes, requests before readiness, and shutdown of an on domain are rejected. MSPI1 and UART/IOM/ADC/GPU/OTP/CRYPTO states are not arbitrarily changed. Pending-request cancellation and fixture Reset use existing power-class behavior; actual power-off/return lifecycle is not yet supported.

No MSPI0 clock, register, FIFO, DMA, external bus, or display model was added here.

## Natural original M55 execution

| Condition | Requests/responses | Status | Next clock-write PC |
| --- | --- | --- | --- |
| Stock 2.4 / active | One each | `0x4000`, on | `0x4e7040` |
| Stock 2.3 / active | One each | `0x4000`, on | `0x4d9c6c` |
| Faceclaw 38 / active | One each | `0x4000`, on | `0x4d9c6c` |
| Stock 2.4 / stuck-off | One each | 0, stuck-off | `0x4e7040` |

All four candidates stopped strictly at clock configuration write **`0x40004110 = 0x000a4210`**. Compared original `str r5, [r1]`, actual register arguments, and guard. Since a clock write was attempted even when power status did not turn on, safe error fallback was not established. This is consistent with the unchecked return found in prior post-call ARM fragments, but does not establish absence of all error handling.

Stock 2.4 active/stuck-off executed 72,932,834/72,933,608 instructions respectively. Reaching the same clock boundary does not mean equal power conditions or execution paths. This is virtual-execution evidence that original code consumed the selected status and advanced. Status responses were not replaced by forced function returns or branches.

The default unattached control stopped at existing `0x40021004 = 0x4e00` and exactly matched prior CPU, instruction count, and all events. Existing advertising 59 commands/60 responses and one VBUS read remained. Stuck-off combinations for older stock/CFW were not executed here.

## Verification and preservation

- Preserved the initial red for the missing MSPI0 argument; then passed 24 shared-bank unit checks and reverified 24 with frozen code.
- Passed 23 existing MSPI1 power checks. MSPI0-unselected blocking and MSPI1 ownership/atomicity contracts remained.
- Five native runs and five saved audits. Initial four candidates failed semantic verdict because bounded-idle expectation differed from the strict clock boundary; originals were preserved. Separate saved audits verified the actual boundary without restarting native execution to erase failures.
- Froze 72 Python dependencies and repeated saved analysis; report and inspector matched byte for byte. Six existing separate-model hashes remained unchanged; startup core was the sole changed model.

Preparation/check tools: `prepare_mspi0_power_candidate.py`, `inspect_mspi0_power_profiles.py`, `verify_mspi0_power.py`. Original, RAM, logs, and pinned manifest remain at `private:simulator/mspi0-power-peer-verification-01/manifest.json`.

Next investigate MSPI0 clock and initial configuration routines as one source/behavior contract, reusing verifiable common portions of existing MSPI1 implementation. Clock, bus, full boot, app loop, integrated display, and physical installation remained incomplete. The web installer, recovery boot, and installation CFW were not changed here; scope v2 remained 13/29 = 44.8%.
