# GPU power-off boundary analysis

Status: static analysis of the exact stock 2.4 image and comparison with public HAL. Before adding a behavior model; full boot, screen, and physical-device verification remain incomplete.

## Findings in the image

Private `simulator/gpu-power-off-research-01/table-and-hal-comparison.json` verifies main hash, then compares resolver 0x494600 PC-relative literals and 16-byte table entries. Call argument 0x14 (index 20) corresponds to:

| Field | Value |
| --- | --- |
| Enable address | 0x40021004 |
| Enable mask | 0x40000 |
| Status address | 0x40021008 |
| Status mask | 0x40000 |

This is stronger evidence than guessing by inserting another HAL version's enum number. Stock 2.4 call at 0x494e96 checks enable and returns if already off; if on, it removes the mask inside a critical section. Entry callee 0x47e6a8 is `mrs r0,primask`, `cpsid i`, `bx lr`, followed by mask store and PRIMASK restoration. Byte analysis is preserved in `stock24-critical-entry.json`. Actual virtual execution's blocked PC 0x494f3e is that store.

Subsequent code includes condition checks, a helper call receiving status address and mask, and a branch specific to argument 0x14. Return meanings of all helpers and the entire call graph were not recovered.

The initial default Thumb decoder stopped at PRIMASK instructions. The skipdata candidate contains undecoded bytes and is not used as evidence of valid instructions. Final bounded decode in M-class/V8 mode continuously decodes 0x494e96–0x494ff4 and confirms `msr primask,r0` at 0x494f42. Initial two files remain diagnostic; use final `stock24-disable-mclass.json`.

## Comparison with public HAL

Pinned Ambiq HAL commit 61b293a `am_hal_pwrctrl_periph_disable` polls power status after removing the enable bit and, on success, handles GPU mode, SPOT state, and clock release. Image processing order corresponds to this structure but does not prove identical source/ABI. In particular, do not reuse current public HAL GPU enum number as the stock image argument.

## Conditions for model extension

The current model blocks off writes while on. Simply permitting them while retaining other GPU state could look like verified retention. Separate power-off request/response, GPU register and ring validity, and reactivation conditions. Presence of RAM contents differs from GPU being able to execute them.

A next implementation can compare off response and stuck-on paths under an explicit hypothesis option and consider blocking GPU MMIO/submission after off until reinitialization evidence exists. Physical delay, register/RAM retention, reactivation, and subsequent submission remain unverified.
