# Explicit Interval Timing Profile and Original GAF Timeout

bw-0429. The first target is whether original stock 2.4 request 2 wait returns to actual caller `0x55496e` after 200,000 iterations. This fault test does not replace normal GAF calculation or successful full initialization.

## Execution contract

Run at 10 MIPS from existing initial main reset through ATT handling. At a whole-machine pause stopping only three owned callbacks of the existing observer in a verified manner, confirm:

- Existing execution rate 10 MIPS, actual HAL mode word 22, field 2.
- Preservation of all general registers, cumulative instruction count, SRAM, STIMER counter, WDT CFG, and virtual time.
- Supply the [independently verified HAL profile](../cpu-memory/hal-loop-time-profile.md) HP 167 MIPS only for this interval.

Original main, MMIO model, board, observer class, 200,000-iteration loop, 5 µs argument, WDT configuration, returns, and TCB/SP are unchanged. The single host input changing CPU execution rate is recorded in `cadence-boundary.json` with before/after state. SRAM before/after is separately preserved. Although source-derived, the profile is not actual cycle-accuracy or physical-clock verification. It does not implement dynamic LP → HP switching across full boot.

Reuse the virtual controller's explicit HCI identity and existing shared IOM power contract. Observe final state only at the original timeout helper and setter continuation; do not treat the host deadline as a firmware timeout.

## Relationship to the overall goal

This test is an explicit fault profile in which the sensor stays busy. Even if original error return is verified, do not extend it into evidence of normal GAF calculation, required initialization, or integrated display completion. All 16 conditions and the progress denominator remain. No actual glasses access, writes, subagents, or external publication occurred.

## Original execution results

In stock 2.4 `gaf-timeout-cadence-native-01`, the first request 2 completed 200,000 queries, and the original wait → helper → setter return path was observed at all points.

| Observation point | PC | R0 |
| --- | --- | --- |
| Original wait pop return point | `0x5559b2` | `0xfffffffc` (−4) |
| Original request helper return point | `0x55408c` | `0xfffffffc` |
| Actual setter continuation | `0x55496e` | `0xfffffffc` |

TCB, LR, and xPSR match at all three points; SP differences for wait → helper → setter are 40/16/0 bytes, consistent with original stack unwinding. Separate final register collection and full core JSON/log agree. The host did not set PC or R0 or skip branches.

The resumed interval was 9.9645566 virtual seconds and approximately 480.3 host seconds. The latter is neither a performance comparison nor a physical timeout measurement. The fault device retained request 1, trigger 1, busy 200,000, pending=true, and 0 normal calculation completions. Timeout return does not mean the pending sensor recovered to normal state.

Watchdog CFG `0x020ce005`, RSTGEN CFG 2, and WDREN=true were retained; reset_due=false. No reset request occurred, so the gate was not evaluated. `allowed_by_gate=false` is not interpreted as the gate being disabled. Guard, CFSR/HFSR, and memory violations were 0.

## Verification and limitations

Registers, instruction count, virtual time, STIMER counter, and WDT CFG were exact before/after profile transition, as was SRAM. Three earlier baseline SRAM snapshots (initial, connection, ATT) were also exact. Main/board/device model/observer class bytes match baseline; only Python's explicit execution-rate input was added.

Twenty-four saved audits and three semantic counterexamples forging caller, iteration count, and return error passed. Source and inputs were regenerated and compared, and a separate verdict avoids presenting completed return as full initialization or normal calculation. Proprietary originals/SRAM are preserved outside Git in `gaf-timeout-cadence-native-01`, and the frozen audit in `gaf-timeout-cadence-research-01`.

This run covered only original stock 2.4. The same timing-profile path for stock 2.3/Faceclaw and subsequent request 4, cleanup, and upper initializer return have not yet been verified. Full boot, normal GAF, and physical timing verification remain incomplete. Overall progress is 8/16=50.0%; E05/E12/E16 are not completed by this result alone.

Next, trace request 4, error cleanup, and upper caller behavior after the actual caller according to original branches. Preserve the existing 10 MIPS baseline and watchdog return evidence. The task of obtaining normal GAF calculation specification/ROM and independent expected values remains separate and is not replaced by this failure path.
