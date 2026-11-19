# Virtual-time IMU reset and continuous original M55 execution

bw-0323. Configuration preservation, reset request, wait, restore, and status consumption from the [original reset contract](imu-reset-lifecycle-contract.md) were implemented in an optional peer profile. Stock 2.4, stock 2.3, and Faceclaw start from original main reset without modifying ARM instructions, returns, or branches. No new CPU PC hook or SRAM write observer was added.

## Model behavior

`tools/renode-imu-identity.cs` retains existing `icm45608-whoami-only` and separately provides `icm45608-reset-lifecycle`. The latter requires two explicit initial 2d/32 bytes and a virtual clock. Physical defaults are unknown. Main tests use synthetic A5/5A and control 12/34; physically valid register bit combinations are not guaranteed.

- Registers 2d/32 can be read to preserve current fixture values.
- `7f 02` starts one limited reset. Configuration values become unknown (-1), not assumed 0.
- Pending ends after 1,000 µs on a 1 MHz Renode virtual clock. Normal fixture sets RESET_DONE; missing-done fixture does not.
- Configuration reads/restores before then, overlapping reset, wrong restore values, and configuration writes outside verified scope are rejected.
- Original code may restore preserved 32, then 2d.
- Register 19 read returns and consumes fixture RESET_DONE bit 7. Read-to-clear is a declared model following the pinned driver's clear intent, not verified physical side effect.
- Peer reset cancels the timer and returns to explicit initial values. IOM controller reset does not cancel the external peer timer. Actual IMU power rail/GPIO reset lifetimes remain separately unknown.

1,000 µs is a **declared completion time** matching the original sleep request, not measured chip completion or guaranteed worst case. Missing-done only omits the flag after time passes; it does not reproduce actual bus hangs or all reset failures. Repeated reset, general IMU configuration, and sensor samples remain unsupported.

## Tests and board connection

`tools/verify_imu_reset.py` runs 44 checks including existing WHOAMI/FIFO checks. It distinguishes 999 µs before completion and afterwards, restore order/value, completion-bit consumption, absence of stale events after cancellation, controller/peer reset independence, and missing-done.

First red was unimplemented reset constructor functionality. First native preparation and board red were rejected before execution because an optional machine parameter was not automatically injected. The existing three-argument constructor was preserved and a separate constructor requiring a virtual clock for reset profile added. Creation in actual platform description was included in unit tests. Failed files were preserved.

## Natural main results

| Input | Initial 2d/32 | reset completion/restore32/restore2d/status read | Next boundary |
| --- | --- | --- | --- |
| Stock 2.4 | A5/5A | 1/1/1/1 | `58236c`, peer-write7ca267 |
| Stock 2.3 | A5/5A | 1/1/1/1 | `57b014`, peer-write7ca267 |
| Faceclaw | A5/5A | 1/1/1/1 | `57b014`, peer-write7ca267 |
| Stock 2.4 value control | 12/34 | 1/1/1/1 | Same next boundary |
| Stock 2.4 missing-done | A5/5A | 0/1/1/1 | Same next boundary, error retained |

Normal runs received four bytes, WHOAMI + two configurations + status, through actual I²C backend, then stopped at the next unsupported request after 11 successful transfer finishes. Twelve IOM commands include the next request rejected by the peer. The 1,000 µs callback required by original source was not deleted or changed to NULL, and the model rejects restore before timer expiry. Original soft-reset preserve → wait → restore → status decision is connected to natural main; this does not mean full advanced initialization completed.

Identity-only control exactly matched bw321 full CPU state and observed events. Six valid original main runs and six saved audits are recorded separately. First board constructor failure is not included as valid native execution. Initial normal/missing-done provisional boundary contract failures were preserved and verified by separate saved audits changing only their capture plans' semantic contracts.

## Important limit after error

Missing-done also reaches the next request, so an identical next boundary must not be judged success. The actual next function's original prologue saves `{r3,r4,r5,lr}`. Saved r5 is 0 for normal/value controls and ffffffff for missing-done. Original instructions ORing soft-reset return before calling the next lookup were linked to saved stack across five captures. No extra CPU hook exists.

Thus error preservation and propagation are confirmed, but fail-stop, safe fallback, and recovery are not. Subsequent access continues despite the error.

## Next unsupported behavior

`7c a2 67` is a three-byte WRITE on the wire but must not be interpreted as an arbitrary sensor configuration value write. It corresponds to pinned TDK `IREG_ADDR_15_8=7c`, `SREG_CTRL=a267`, and original caller `read_reg(a267,1)`/bit-1 extraction. It is address selection for an internal-register endianness lookup. IREG ready/data lifetime and return byte are not yet supplied.

Next analyze indirect address, ready/data, and endianness cache as an original transport unit, then extend the model. Afterwards continue nonzero main draw and framebuffer/576×288 viewer. Overall goals remain web installation, Faceclaw CFW, recovery boot, and integrated simulator.

Frozen source, tests, failures, captures, audits, and saved-error verification are preserved in private `simulator/imu-reset-model-verification-01/manifest.json`. Product completion 13/29=44.8%, scope v2 remain. No physical access, installation, or persistent writes; full boot, app loop, and UI remain incomplete.
