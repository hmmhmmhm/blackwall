# Original ring report reception contract

bw-0455 · E11 partially complete. Confirmed **stock 2.4 natural main reset → virtual opposite-temple UART0 ring relay → original parser/registered service → original ring task → source 4/code 1 delivery → return to the original caller**. Direct R1 BLE connection, execution of the ring's full firmware, downstream app/UI consumption, and screen output were not validated at this stage. Overall acceptance remained 10/16 = 62.5%.

## Input boundary

Do not reuse the touch MCU's IOM5 report as ring input. Service `0x90` in the original registration table has a callback that places received data in the ring queue. This path delivered a ring report relayed by the virtual opposite temple. It is an explicitly declared virtual-peer contract allowed by the objective, not a claim of HCI input emulating an actual R1 BLE notification.

The original ring-report fixture is 11 bytes. The value used here is `00096100020aa7e8030000`: type 2, aux 10, speed 167, and ring tick 1000. Tick is in the ring's original uptime units; do not convert it to a phone epoch or measured milliseconds. The UART payload prepends the original channel 1 listener's kind 9 header `<4H>(0x0901,0x90,0,11)` to the report. The frame with ID `0x9010` and channel 1 is:

`0190100013000156fc0109900000000b0000096100020aa7e80300006a3e`

The existing frame codec and original listener structure were compared, and the host put only these 30 bytes into UART0 through the verified RX FIFO API. It did not directly invoke the parser or callback, or write guest queue, TCB, PC, branch, or readiness state. Every PC in the service-delivery path after the parser was not observed in this run; the original registration table/call connections and actual entry into the ring handler jointly support the conclusion.

## Version-specific source contract

| Item | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| Ring receiver | `0x4eeec0` | `0x47911a` |
| Receiver caller return | `0x4ef2be` | `0x479518` |
| Common slider delivery | `0x5788a0` | `0x4df264` |
| Last ring tick storage | `0x200774e4` | `0x20077cf0` |

For each raw image, the unique function bodies, actual BL instructions, service `0x90` row/callback, and kind 2 queue wrapper were located and compared. Faceclaw branches from `0x47911a` to `0x7d5800`; in this isolated test based on natural SRAM it actually executed the helper → `0x7d5812` fallback → stock body. The lease-held, phone-delivery, and left-bridge branches were not execution-validated.

The original arguments for each wire type are below. Actual R0–R3 arguments are recorded rather than inferred names.

| Wire type | Source | Original input code | R2 / R3 |
| --- | --- | --- | --- |
| 0 | 4 | 3 | 0 / 0 |
| 1 | 4 | 0 | 0 / 0 |
| 2 | 4 | 1 | 0 / 0 |
| 4 | 4 | 5 | aux / speed |
| 5 | 4 | 4 | aux / speed |
| 8 | 4 | 14 | 0 / 0 |
| 9 | 4 | 17 | 0 / 0 |
| 10 | 4 | 13 | 0 / 0 |

## Duplicate suppression and independent ARM tests

When the last tick is nonzero, the original suppresses ordinary reports with an unsigned difference below 100. Types 8 and 10 are exempt. Type 10 does not update the last tick; type 8 does. Differences of 99/100, 32-bit wrap, a value below the previous tick, unknown types, and reports with reserved bytes were compared. Even if an unknown type or reserved byte prevents action delivery, the tick may already be updated. Interpreting gestures or deduplicating on the host first would lose this original behavior.

Across three originals × 19 scenarios, with observation off/on, 114 **isolated Unicorn M7 runs of original ARM code** passed 190 checks. No other firmware callee was stubbed and the PC was not changed during execution. Delivered reports stopped immediately before entry to the actual slider function; suppressed/unknown/null inputs were checked through the receiver's actual return. Final CPU, SRAM, and work values matched with and without observation. These were not unit tests of natural main: they used synthetic report/caller/last-tick fixtures and the remaining SRAM from natural execution.

The receiver's source-length check is not an exact 11-byte check. The path for lengths of at least 8 reads the 32-bit tick at +7, and some classification paths remain for shorter lengths. This virtual peer supplied exactly 11 bytes. Do not extend this to a claim that malformed-length protection in the full higher-level receiver or an actual device vulnerability was established. Do not mix RingProtocol's separate health CRC32C protocol with this input report or the UART CRC.

## Natural M55 execution

Only stock 2.4 was newly validated. It used the existing 10 MIPS and explicit GAF-parameter profile; this does not mean normal GAF calculation is implemented.

- UART0 read the actual 30 bytes and pending became 0. Actual ISR/owner counters recorded exception 31 entries increasing from 10 to 13, and the new observer recorded three entries. This is **external IRQ15**, distinct from external IRQ31.
- The original receiver received the original 11 bytes and delivered source 4/code 1/R2 = R3 = 0 to the original slider function. The original updated the last ring tick to 1000.
- The current task in the active linked task graph was `ring`, priority 46. Handler and caller had the same SP and TCB and returned to Thread context.
- All SRAM, R0–15, and virtual time were identical before and after UART injection. CFSR/HFSR, memory violations, trace overflow, and all 17 recorded strict guards were 0.
- All 23 saved-run audit checks passed. The model was unchanged; the existing UART RX FIFO/timeout implementation was reused. All owned processes were removed.

## Failure and observation boundaries

The first harness used the nonexistent name `TryEnqueueRx` and failed before injection. It was corrected to use the existing `TryReceive(data,powered)` and actual power-state check, and the failed directory was retained.

The second run confirmed receiver, slider, and caller but recorded zero additional UART IRQ hook entries because it selected the wrong raw vector index. It was not revised into a success. A third, separately configured run recorded the existing UART owner's `IrqHandlerAddress` and exception counts and included the XIP guard. The two configurations had exact observed receiver trace, entry/exit, and final full SRAM. This narrow comparison is not proof that all observation hooks are non-intrusive.

Twenty-seven static source checks verified seven files' Git blobs/SHA for Faceclaw `70ec2a0d6afd92e8185234e57ab013fcb596bf4d` and g2flash `845f665e0dfdcfd06b7d3a294388de6f17a5bd59`, the three original source structures, and upstream ABI guards. Existing GPL-3.0 provenance records for both repositories were retained, and analysis originals remained private. Candidate firmware was not silently switched to another, newer commit.

Outside Git, `simulator/ring-input-ingress-research-01/` retains source, contracts, isolated ARM validation, harness versions, and audits; `ring-input-native-{01,02,03}/stock24/` retains failures and actual runs. `simulator/ring-input-ingress-manifest.json` pins input, result, and document snapshots.

The next work was to compare natural stock 2.3/Faceclaw reception and error inputs for the same relay, then connect ring-generated downstream messages to the original app-consumption path and integrate them into a public scenario. The direct R1 BLE controller contract, other gestures and reset lifecycle, UI/pixels, and normal GAF dependencies remained outstanding. No physical access, flashing, subagent use, or external publication occurred.
