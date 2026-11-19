# TIMER7 PWM Original Function Contract and Implementation Boundary

Work `bw-0233` in progress. Existing native mains for stock 2.4, stock 2.3, and Faceclaw38 strictly stopped at TIMER7 CTRL7 `0x400082e0` read. This verification is **isolated original-function execution** to establish evidence for modeling subsequent behavior. It is not a new integrated main run or a result passing that stop.

## Evidence obtained

`tools/inspect_timer7_contract.py` maps main from pinned bundles read/execute-only at original addresses. It prepares each function entry, call arguments, synthetic stack, and MMIO backing memory, then executes until original `bx lr`/`pop pc` return. It does not force internal PC, branches, or return values or intercept calls. The actual interrupt-mask callee of the output configuration function also executes, confirming restoration for PRIMASK=0/1. MMIO backing memory in this test is not a timer behavior model.

| Function | Stock 2.4 | Stock 2.3 / Faceclaw38 | Confirmed |
| --- | --- | --- | --- |
| Configuration | `0x47d372` | `0x478646` | CTRL disable → PWM `0x40` → MODE `0x100` → CMP0/1 `0xffffffff` → retain CLR `0x42` |
| GPIO output selection | `0x47d5c8` | `0x47889c` | GPIO145 selector 14; preserve other settings in same word and target byte bit 7 |
| Set CMP0 | `0x47d606` | `0x4788da` | Write argument 24000 to `0x400082e8` |
| Set CMP1 | `0x47d620` | `0x4788f4` | Write argument 16800 to `0x400082ec` |

The output configuration HAL contract updates only seven bits at `(pad % 4)*8` in `OUTCFG0 + (pad >> 2)` word. Thus GPIO145 is `OUTCFG36`, **address `0x40008110`, bits 8..14**, and selector 14 is TIMER7 OUT0. GPIO144..147 and both PRIMASK states were checked. GPIO224 and selector 40 return error 6 without writes in original validation. Reserved internal channels 14/15 return error 3 without writes in configuration and both comparator functions. This does not mean every invalid argument outside this scope was verified.

Across three inputs, **60 isolated function runs + six pinned source/definition checks = 66 checks** passed. Original SHA, function addresses, and actual write records are preserved outside Git in `simulator/timer7-contract-02/report.json`. First `timer7-contract-01` failed from a host type error passing Python bytearray to Unicorn mem_write and was excluded from final evidence. All 66 ran after conversion to bytes.

## PWM semantics and remaining assumptions

Pinned Ambiq HAL/header/register documentation confirms PWM function value 4, CMP0 period, CMP1 low phase, OUT1=~OUT0, and TIMER7 IRQ74. Source is zephyrproject-rtos/hal_ambiq commit `61b293a49db34030c545f99101f7ebf6a3050314` in existing `timer-source-research-01/sources.json`; the inspector pins HAL/header SHA.

Static analysis of the original PWM wrapper points to channel 7, clock 0, 1000 Hz, duty 30, and GPIO145 configuration. If nominal HFRC is 96 MHz/4, period is 24000 and low phase 16800. **This execution supplied those values to comparator setters; it did not execute the entire floating-point PWM calculation helper.** Actual HFRC frequency, output period, and load purpose were not verified. What physical function GPIO145 controls is not established.

## Required model changes

Current `renode-timer14.cs` exposes only channels 0/14, and the original engine logs an error when PWM is selected. Upstream Apollo4 engine's OUTCFG array has only 32 words (GPIO0..127), so GPIO145's word cannot be handled by that array. Merely storing CTRL7 or resetting the counter to 0 on every CMP1 does not meet this contract.

The next implementation should jointly verify these as an explicit candidate of the existing common engine:

- PWM low/high phases and repetition at CMP0 without early reload at CMP1. Confirm nominal 24 MHz initial clock 0 is also applied to the actual counter.
- CLR retention, restart, disable, global gate, reset and comparator state, TIMER7 IRQ74, and separation of pending state for channels 0/14.
- Preserve GPIO145 selection in OUTCFG36. Report only the implemented/verified scope separately for output-selection latch, virtual waveform, and actual GPIO/pad electrical output.
- Byte invariance of existing engine default output and channel 0/14 regressions. Do not retroactively inject the new candidate into historical audits.
- Finally run all three originals from reset with the same candidate manifest and compare existing observations and next strict boundary.

At this contract-verification point there was no model change or new native main run. Later [PWM candidate model and integrated execution](timer7-pwm-model.md) completed implementation, 37 unit/122 regression checks, and three originals plus one off control. Original initial configuration passed, but original main's TIMER7 start, full boot, integrated display, and physical installation/recovery remain incomplete; product fulfillment remains 13/29 (44.8%).
