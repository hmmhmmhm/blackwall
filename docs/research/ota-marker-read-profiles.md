# Virtual OTA Marker Reads and Original Main Branches

Task bw-0282. The [marker source contract](ota-marker-state-contract.md) was connected as an immutable read-only fixture. It distinguishes `cleared=ffffffff`, `pending=55555555`, and the default `unknown`. These are not evidence of physical-device state, installation approval, or freshness; marker writes and update/reset were not implemented.

## Integration

`BlackwallOtaMarkerRead` supports only the three direct word-load sites in the original startup load and setter. It checks address 7fe000, PC, and actual R0 or R4 context together. The value is pinned to the profile and does not change with read count or setter execution.

It is connected as an optional reference to the existing tail owner `BlackwallKeyDbSlotStorage`. Without the reference, existing behavior remains; the unknown fixture also supplies no value. Byte/2-byte/8-byte accesses, neighboring addresses, direct host reads, and all writes remain rejected. The allowed range was not arbitrarily expanded to the 16-byte write template or 32-byte debug dump. Parent reset clears only the child's diagnostic counters.

## Original M55 results

| Input | Actual marker consumption | Next boundary |
| --- | --- | --- |
| cleared, stock 2.4/2.3/Faceclaw 38 | startup 1 + setter 2 = 3 reads | New GPIO117 word read |
| pending, stock 2.4 | startup 1 + setter 2 = 3 reads, prepare 16-byte clear | cache 40021014=3f write |
| unknown, stock 2.4 | 0 data supplied | Existing 7fe000 read |
| fixture off, stock 2.4 | 0 data supplied | Existing 7fe000 read |

For cleared, the original equality branch skipped MRAM programming and continued into subsequent code. The initial stock 2.4 plan expected the older HCI write-helper PC, but the actual new read PC was `0x4dd1d4`. The failed original report/plan was retained and corrected through a separate saved audit. Execution was not restarted and PC was not forced. Stock 2.3/Faceclaw stopped at `0x4c9990`.

The new consumer was identified by source loop bound 1000, address 40010410, and bit 21 extraction. Although it reads the same GPIO117 word as the initialization HCI helper, it is a different consumer, so the existing model rejected it. No new ready value is supplied here and controller initialization is not assumed complete. This boundary's protocol owner and IOM/IRQ/queue contract require further analysis.

In the pending snapshot, the actual 16-byte R5 buffer was all ff, R6's MRAM word offset targeted 7fe000, and R7 was four words. The stack's normal program constant 12344321 and cache caller return address also matched the original MRAM wrapper. Actual programming had not executed and the pending fixture was unchanged. Do not report clear preparation as completed marker modification.

## Verification

- The RED result for the missing new type was retained, and the final component's 179 conditions passed. These include the previous 148 keydb conditions and marker address/PC/register/profile, read value, reset, parent connection, and rejection of host, other widths, and writes. The initial 173-condition result was superseded by the final scope.
- Six native runs and six separate saved audits. The first stock 2.4 cleared run retained its execution success and failed PC-meaning prediction; the other five also passed their initial contracts. Unknown and off exactly matched the original source CPU, instruction count, events, and boundary.
- Six saved analyses compare the new GPIO read and pending's actual 16-byte arguments and stack against original code/context. The earlier 63 original ARM marker conditions were reused after rechecking the source pin.
- Private `ota-marker-read-verification-01/manifest.json` retains the two models, unit tests, executions, audits, prediction failure, and 25 pinned analyzer dependencies. The analyzer is rerun from a pinned copy to verify identical original reports. Main/SRAM are outside Git.

The new marker fixture was not connected to the web gate or a physical writer. The existing complete web installation block and unimplemented marker-specific hardware gate remain unchanged. No device, actual MRAM, OTA, or pairing was operated.

## Next unit

Compare the new GPIO117 consumer's original caller/transport and queue/IRQ with the initialization-stage peer, then extend the response model. Pending clear, MRAM cache/program, and interruption recovery remain incomplete. Do not interpret marker clear or successful use of this read fixture as full boot success.

Overall completion remains 13/29 = 44.8%. Actual app loop, integrated 576×288 display, and physical-device recovery remain incomplete.
