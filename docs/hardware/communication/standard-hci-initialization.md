# Standard HCI mask initialization and explicit address readback

bw-0289. Virtual transmission and reception of four standard commands after vendor initialization were connected in natural mains of stock 2.4, stock 2.3, and Faceclaw38. The next information query was prepared after cumulative command/reply 10/10. Overall 13/29=44.8%; full boot and integrated display remain incomplete.

## Original command and response contract

| Order | Original queued packet | H4 length of response fixture |
| --- | --- | --- |
| Set Event Mask | `01010c089088000200800020` | 7 |
| LE Set Event Mask | `01012008ffff7f0000000000` | 7 |
| Set Event Mask Page2 | `01630c080000800000000000` | 7 |
| Read BD_ADDR | `01091000` | 13 |

The first three return status only. Address read requires six public-address bytes in addition to status. [Bluetooth Core 6.1 §7.3.1, §7.3.69, §7.8.1, §7.4.6](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html). The supplied address matches the six bytes previously specified for virtual `fc43`. It was not collected from an actual controller and is not evidence that a physical controller retains or returns it.

Optional `standardInitialization` in `renode-em9305-reset.cs` defaults false and can be enabled only with an explicit vendor/address scenario. It supports exactly four packets and normal responses of fixed length 7/7/7/13, not the subsequent information query. Vendor acceptance count and records are limited to three so standard commands are not mixed in. Existing GPIO state, CS commit, and IOM chunk validation are reused.

## Differences confirmed in software controls

Synthetic function tests connecting original pop → parser → upper handler ran for each image. Unicorn M7 used original ARM and verified complete SRAM. Synthetic entry/register/stack and assumed responses distinguish these from natural Renode runs.

Four normal responses and a status-1 error on the first mask prepared the next `2002` query. However, a completion event with opcode `0c02` for the first mask yielded no next command. The no-event control also yielded none. Previous vendor-stage opcode control results cannot be generalized to standard commands; this does not guarantee validation of all other states or commands either.

Initial analysis expected wrong opcode to continue as in vendor handling and failed the next-packet check. Actual ring used 0 confirmed no subsequent command, and the contract was corrected. Original branches/code were not changed to match the prediction. Twelve software scenarios, 27 assumed completion events, and three no-event controls were retained.

## Natural main and regression verification

All three images from original reset showed command/reply 10/10, frame 26, IOM 52, standard accepted 4, vendor accepted 3, and application drain 8. The three standard mask commands have length 12 and each split into two command frames at capacity 9. Address query is length 4 and received 13-byte response.

After wraparound, TX ring was `write offset260, read offset0, used260, capacity2080, stride260`; actual queued packet was `01 02 20 00`. R8=4, R9=0, R10=actual record pointer and SRAM bytes were checked. The same ring offset and transfer-helper PC as initial Reset recur, but pending packet and cumulative transmission history differ. Next unsupported write-ready PC is 2.4 `501676`, older versions `549fce`.

The next command is LE Read Buffer Size, an information response not replaceable with status alone, so its transmission/response were not yet supported. [Bluetooth Core 6.1 §7.8.2](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html). This does not verify actual controller information, full BLE initialization, physical PHY, full boot, or display.

Stock 2.4 with the standard feature off exactly matched prior CPU, instruction count, events, and boundary; command/reply 6/6, frame 15, IOM 30. It did not exchange standard commands. Final unit tests covered 182 default, 328 two-byte split, and 58 existing default conditions. They checked constructor requirements, invalid packet/receive length, pre/post-CS commit, address-byte match, vendor/standard record separation, next unsupported command, frame totals, and prohibition of reset rearming.

## Evidence and next work

`prepare_standard_hci_candidate.py` creates a separate plan from the verified source contract and does not write the existing board configuration containing an address outside the private simulator. Output outside it is rejected before source reads, and existing files are not overwritten.

Pinned in the simulator outside Git:

- `standard-hci-source-01`, `-02`: 12/27/3 software results and identical pinned-copy reanalysis.
- `standard-hci-unit-03`, `-02`, `standard-hci-legacy-01`: 182/328/58 conditions.
- `standard-hci-main-01/{stock24,stock23,cfw}`, `standard-hci-control-01/stock24`: all four native runs passed semantic contracts.
- `standard-hci-saved-audit-01`: four saved audits.
- `standard-hci-contract-01`, `-02`, `standard-hci-verification-01/manifest.json`: identical saved analysis, pinned Python 36, models 4, and source/unit/native/audit SHAs.

IOM/keyDB/marker and web gate are unchanged. Command names/formats were checked against the Bluetooth SIG search index; direct full-page find timed out. This is not reported as a full-page review.

Next determine how `2002` response length and buffer/credit values affect original flow control and subsequent initialization. Explicitly separate mock values without assuming actual chip values are known. The natural app loop/display initialization and original glyph/GPU integration goals remain. No glasses/case access, OTA, persistent write, or installation occurred.
