# Original app consumption and UI wake from Ring input

bw-0457 · E11/E09 partially complete. **Stock 2.4 natural main reset → virtual ring relay UART0 RX → original ring task → actual 0x108 request/peer ACK → registered app callback and state update → app 1 request/display response → original UI callback entry** was confirmed. No new CFW feature or device model was implemented; the required power lifetime used the existing verified optional shared-IOM profile. UI callback return, rendering, and pixels remain incomplete. Overall acceptance is 10/16=62.5%.

## Original request and actual consumption

The type 2/tick 1000 report from [bw456](ring-family-and-duplicate-contract.md) was delivered through the existing UART0 RX FIFO. After ring receiver caller return, a service 0x108 request was found in actual UART DMA transmission. Its contents were original `<4H>(0x0901,0x108,0,12)` and `<3I>(source4,code1,0)`; the host created neither this request nor pending record.

The virtual peer sent one 12-byte ACK on channel 0/content `0x0a` for actual request ID `0x800a`. Original parser, reply callback, registered 0x108 callback `0x578ce6`, and input helper executed, returning R0=0 to the original event caller with the same SP/TCB and Thread context. Original helper input was role 4/code 1/OS tick 5288. Actual app state changed role 255→4 and tick 0→5288. This OS tick is distinct from original ring tick 1000.

The original idle path produced an app 1 request. Source descriptor ID was `0x800b`, channel 2, length 8, packet `0201010000000000`. Actual DMA frame and CRC were checked. Original UART timeout/parser consumed the virtual peer's single 12-byte channel 0/content 2 response. Total RX was ring report 30 bytes + two responses of 12 bytes each = 54 bytes, pending 0.

Original UI producer → registration-table dispatch → app 1 callback `0x4b7a58` was reached. Actual current linked task was `ui_task`, priority 44, and callback entered with event 2/content length 0. Stopping at this address is not evidence of callback completion, initialization completion, or pixel output. The host did not set original PC, branch, TCB, or readiness.

## Actual power boundary and existing profile reuse

The default run strictly stopped after UI message production at `PC0x494d78`, writing `PWRCTRL.DEVPWREN(0x40021004)`. Address/PC alone could not identify the peripheral. Initial IOM5/MSPI0 hypotheses were corrected as wrong after collecting actual values; hypotheses and failure material were retained.

The existing post-stop power exporter collected the following without changing execution:

| Item | Actual value |
| --- | --- |
| Current request / proposed value | `0x8e20` / `0x8f20` |
| XOR / target | `0x100` / IOM7 bit 8 |
| IOM7 | off-requested, request 0/status `0x100` |
| IOM4 in same HCPC | on, request=status `0x20` |
| MSPI0 | powered-off, request=status 0, not targeted by this change |
| Buck / current task | active / displaydrv_mgr_task |

When the same domain remains on, original HAL skips the status poll used for the last user. This is a local gate/reopen case supported by the [existing shared-IOM power contract](../power/iom-shared-power-lifecycle.md). The runtime default board did not have that option. Existing `compose` and `board_profile` in `tools/iom_shared_power_model.py` were used unchanged and explicitly applied to five IOM owners from reset. No runtime phase or guest poll was added. This existing composition checks power class SHA and owner branches; new power-model code changes were 0.

Full SRAM before/after profile application was exact at five checkpoints: before input, ring caller, before ACK, app wake, and display send. App request/ACK stage JSON was also exact. Thus original app consumption in this control interval was not changed to avoid the power boundary. After the existing profile handled IOM7 resumption, execution reached original UI callback entry. Existing unverified physical power/retention accuracy limits remain.

## Verification and failure preservation

- Three new M55 runs: initial strict boundary, post-stop power collection, and explicit shared-IOM profile. The earlier aborted machine was not resumed.
- Final full SRAM/model before and after adding the postprocessing exporter were exact. The initial strict capture remains preserved with UI not reached and guard 1.
- All three inputs had identical full SRAM, R0–15, and virtual time before/after injection. Final successful configuration had CFSR/HFSR, memory violation, observation overflow, and all 17 recorded guards at 0. All owned processes were removed.
- Forty-five audit checks passed, including request, CRC/ID correlation, original callback return, state change, UI entry, exact existing source-profile composition, power XOR, and five prefixes. This count does not raise the overall completion score.

Plans, generators, runners, analysis, and audit are outside Git in `simulator/ring-app-wake-research-01/`; actual board, source, snapshots, and logs are in `ring-app-wake-native-01`, `ring-app-wake-power-native-01`, and `ring-app-wake-shared-native-01`. They are pinned by `simulator/ring-app-wake-manifest.json`. No physical device, flashing, subagent, or external publication occurred.

Next connect the verified shared-power profile and ring→app consumption contract to other originals/public scenarios. Natural UI callback completion, guest frame, continuous display, and normal GAF computation remain separate key dependencies. Do not proceed merely by changing the time limit of the same frozen-GAF run or forcing original readiness.
