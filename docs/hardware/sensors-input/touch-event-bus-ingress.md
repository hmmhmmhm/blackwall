# IOM5 touch frames and original M55 task consumption

bw441. In original main reset runs of stock 2.4/2.3/Faceclaw38, **explicit 16-byte IOM5 input → original `input` task → wear-state update/slider dispatch → subsequent execution of original caller** was connected. The ABI substitutions of the earlier [isolated ARM contract](touch-event-frame-contract.md) were not used on this path.

This is startup input explicitly specifying initial GPIO27 low and read budget 1. **It is not runtime input with injected GPIO edge/IRQ, completed app/UI consumption, normal GAF initialization, or full boot success.** E11 remains partial; overall 10/16=62.5%, API screen 3/6.

## Device model change

Only optional `eventFrameHex` was added to existing `BlackwallIomRegisterProbe`. Exactly 16-byte hex is allowed only with `touch-startup-config` and `eventPointerProbe=true`. If omitted, existing unknown-event-read rejection remains. Version, threshold, and configuration responses retain existing contracts.

With register 03 selected, four bytes are returned only when the existing IOM engine's read-only CMDSTATUS indicates a read command and 16/12/8/4 bytes remaining. Do not confuse the full 16-byte request with one 4-byte peer request. Each chunk is newly copied from a private immutable original frame. Once all 16 bytes are delivered it is exhausted; rereads and reuse with a new pointer03 are rejected. Existing contracts for other registers remain.

CMDSTATUS is checked as an existing read-only engine value; no separate guest read counter is added. Owner IOM engine and shared GPIO/core model are byte-unchanged. A separate observation class only reads registers, SP/LR/TCB/xPSR, and actual frame at original function PCs; it does not write CPU/branches/returns or TCB. No universal observer noninterference is claimed.

IOM controller reset does not replay exhausted peer input. Explicit peer reset reprepares the selected test input. Complete contracts for intermediate partial-transaction reset, physical touch MCU reset/ACK, and GPIO clear delay were not verified here.

## Actual three-original execution

Input is `02 40 0a a7 34 12 cd ab 01 80 ff ff 5a c3 17 e9`. Each image's raw main and initial SRAM/ITCM are byte-identical to existing reset inputs. New model delta is one peer and independent observer only. Memory snapshots were collected after guest's existing strict stop.

| Result | Stock 2.4 | Stock 2.3 | Faceclaw38 |
| --- | --- | --- | --- |
| Actual task | `input` | `input` | `input` |
| TCB | `0x200745f0` | `0x2007515c` | `0x2007515c` |
| 4-byte chunks / frames completed | 4 / 1 | 4 / 1 | 4 / 1 |
| Frame on original stack | 16 bytes exact | Exact | Exact |
| Wear state / notification arguments | 2 / `[3,2]` | Same | Same |
| Actual slider dispatch arguments | `[1,4,10,167]` | Same | Same |
| Next strict PC | `0x49668c` | `0x48a7a4` | `0x48a7a4` |

The last boundary is the second lookup of GPIO27 word `0x40010404`. Budget 1 was exhausted, so unknown was not continually filled as high/low. The same `input` TCB and original 1024-word stack range were retained; IPSR at all observation points was 0. Stack difference from handler entry to after read was 128 bytes; only 28 pushed bytes remained at epilogue. Actual function returned and reached subsequent GPIO HAL. Observations are Thread mode; memory protection and system-control violations were 0. CFSR/HFSR were not separately collected, so absence of all CPU faults is not claimed.

On this path original read helper, IOM HAL, memcpy, handler, wear notification, and slider dispatch actually executed on M55. Entry arguments of dispatch and subsequent handler return were confirmed, not final UI consumption of the event. Virtual processing time is not reported as physical latency.

## Error and disabled controls

In the same stock 2.4 run only the first byte was changed to 3. IOM's 16-byte transfer completed, but original code traversed only handler entry → read return → epilogue. Wear notification and slider dispatch were zero; state remained 0.

The first plan for this input expected the normal frame's GPIO27 reread boundary and had **semantic passed=false**. It actually reached pin136 clear boundary `0x4966ec / 0x40010468 / write0x100`, previously established by [GPIO unchanged-latch write](../power/gpio-unchanged-write-policy.md). Original execution and failed report were unchanged; only semantics were separately audited using existing pinned frontier evidence. Saved audit passed with zero firmware reruns. Error-frame discard is not interpreted as normal boot success.

A separate stock 2.4 option-off run was exact in CPU, instruction count, existing events, and boundary at the previous peer-read stop. This controls preservation of old behavior when no new frame is supplied, not universal neutrality of every observer/profile.

## Checks and evidence

- Five new original M55 runs: three normal, one error, one off. Initial frontier judgment failure in error run is preserved.
- Final 59 device-unit checks: actual IOM transfer/completion IRQ, invalid full length and out-of-command read, exhaustion/reuse, missing input, reset distinction, and invalid constructor inputs.
- Existing startup 41 and event-pointer unknown 44 checks passed. Existing pointer/version behavior was also checked in common prefixes of these scenarios.
- Shared runner 13 checks passed. This does not claim all project tests ran.
- First red was missing `eventFrameHex` constructor entry. First extended unit run failed completion IRQ because its fixture did not reconfigure INTEN after reset. A run explicitly setting INTEN1 passed 55 checks, then four negative constructor cases brought final passing checks to 59. Failure/intermediate logs were preserved.

Private material is `simulator/touch-event-bus-research-01` (plan, execution/semantic verifier, reports), `touch-event-bus-native-01` (three originals/off), `touch-event-bus-invalid-01`, `touch-event-bus-invalid-audit-01`, and unit folders. `touch-event-bus-manifest.json` pins input/output, original source, and final source snapshot by SHA/size. All completed owned-container journals are removed. No physical access, writes, subagents, or external publication.

## Next dependency

Next, rather than multiplying startup-packet variants, **connect GPIO27 IRQ registration/task notification in the current runtime to this IOM5 input**. Do not reimplement pin136 latch already solved in the existing model. Compare callback/IRQ mask and pending/clear to original initialization, wake the `input` task via a device-boundary edge, and verify consumption through app/screen. Do not arbitrarily register GPIO27 clear timing or physical idle polarity as defaults.
