# From original BLE transport input to the sync request queue

bw367, E05/E11/E13. **The original ARM path from serialized TPL input → registered callback → SendDataToBoth → actual transmit queue** was verified in 53 isolated M7/API scenarios across three originals. UART transmission, request ID generation, BLE connection/authentication, device input, and natural main completion were not executed. Raw firmware and peripheral models were unchanged.

Later [bw368 native request production](../../architecture/tpl-native-request-production.md) connected the queue producer below to ID/frame/DMA generation by the original M55 task and return to the caller. The following describes the scope of the isolated bw367 contract.

## Actual path producing original requests

In bw366, the test caller directly invoked allocator/start/chunk/finish. In the original, `SendDataToBoth` performs allocation, packet generation, queue put, and UART task event notification. The UART task's 469b24 (stock24) loop removes a node from the actual transmit queue and calls start/chunk/finish. Type 2 is the display branch; type 1 is application data.

`TPL_Init` registers SendDataToBoth at +4 in the actual SRAM callback table. The normal data branch of `APP_BleEusWriteCb` passes transport 0 and the stack's data/size to TPL_ReceivePacket. After input validation/CRC, original TPL branches to the table+4 callback based on header[7] bit 5. This source relationship was bound together with the actual callback address and queue handle in the snapshot.

| Boundary | stock24 | stock23 | Faceclaw38 |
| --- | --- | --- | --- |
| EUS write callback | 4e3d8c | 4d6938 | 4d6938 |
| EUS receive call | 4e3de8→4dea98 | 4d6994→4cf470 | 4d6994→7d2638 |
| Original TPL entry | 4dea98 | 4cf470 | 4cf470 |
| Registered SendDataToBoth | 46a79c | 46a860 | 46a860 |
| Callback table | 200748f0 | 2007353c | 2007353c |
| Sync transmit queue slot | 200775dc | 20077dc8 | 20077dc8 |

The EUS callback has a branch that handles handle 847 separately. Upstream ATT/security checks and the actual normal characteristic handle/connection were not verified in this test. This callback analysis is not evidence of successful BLE authentication or authorization to bypass security. The presence of the same original function does not mean virtual BLE device input is connected.

Later [bw369 ATT registration verification](../communication/eus-att-device-ingress-contract.md) found that Faceclaw's actual write callback is an additional wrapper at 7d5924. The EUS address above is the original function symbol, distinct from the live registered pointer.

## Excluded candidate and version differences

The first candidate found, 5a9af8 (stock24), was registered in current SRAM but was a UART shell command named udata. The function splitting string tokens was not assumed to be a protobuf field parser. Shell/product-test commands are not used as normal phone input.

Faceclaw has no BL directly calling original TPL. The EUS call at 4d6994 is patched to hook 7d2638. This hook checks transport 0, valid pointer, minimum length, and AA marker, handles service F0 separately, and tail-branches other input to original 4cf470. The actual target of the original movw/movt/bx was verified. The Faceclaw test starts at this hook entry, so the fallback is not replaced by the host.

For the same service F0 input, stock23 queued it through the normal SendDataToBoth path, while Faceclaw stopped at the custom handler entry boundary. This is an actual raw ARM version difference. Full validation/effects of the custom command were not executed, and the new candidate comparison E15 is not fully complete.

## Verified single TPL frame contract

Test input is an 8-byte header + payload + little-endian CRC. The marker checked by the original is AA, header[3] is payload length + 2, header[4]=1 selects the single-frame branch tested here, header[6] is the 1-byte app/service, and header[7] bit 5 routes to Both. Other fixed header values are not promoted to a full protocol specification.

The CRC helper's third argument 0 means no initial CRC pointer, not seed 0. In this case the original starts at FFFF. The actual ARM CRC helper was run and compared with Python binascii.crc_hqx(payload,FFFF). This confirms the existing reference repository's payload CRC evidence in the current firmware and is distinct from the separate UART sync CRC (initial 0, a001).

Each image was tested with app 0b/06 and payloads of 0/4/16/253 bytes. Execution ran from the original TPL entry (hook for Faceclaw) to immediately after the actual return from SendDataToBoth. The host does not create heap nodes, callbacks, or queue items, or stub original internal callees. The original produced the following:

- The existing transmit queue message count increased by exactly 1. The queue may already contain other pending entries, so 0 was not assumed.
- The actual queue write slot contains a node pointer created by the original allocator.
- The node is type 1, length 8+payload, and the packet matches `01 09 | app(le16) | 00 00 | length(le16) | payload`.
- The node's completion callback is not 0 but the original completion function registered by TPL. Execution of this callback has not yet been tested.

App 0b is not automatically expanded to display app 010b. The contracts for the 1-byte app in TPL input and UART data/display types differ, so the next step must verify that the app handler actually produces a display request.

Failure/branch controls confirmed zero queue change up to the original CRC failure branch for six CRC alterations per image; one each per image of marker error return 10 and short-size return 11; and a branch to the registered peer callback entry when bit 5 is clear. Final return from the CRC error handler and the peer callback body were not executed. The 53 comprise 24 normal + 18 CRC boundary + 3 peer branch + 6 error return + 2 F0 version-difference scenarios. They are not a measure of time, physical BLE, or overall functional completion.

## Failure preservation and reproduction

Source01 failed by assuming the completion callback was 0. The node from the same input was read to identify the original TPL callback, and the run result was preserved. Source02/03 failed on Faceclaw by assuming every version had an original direct TPL BL. After discovering the actual hook/fallback, source04 verified 52 scenarios, and source05 added the F0 stock control for 53. Results of the two earlier versions are not used as evidence of Faceclaw equivalence.

```sh
<private-python> tools/probe_display_root_ingress.py <simulator> <new-private-output>
```

Inputs are the pinned main/SRAM from the bw366 native capture. The capture manifest and each SHA are checked. The source05 report, tools, failure diagnostics, and frozen verification are linked at private:simulator/display-root-research-01/manifest.json. Proprietary main/SRAM is not copied into Git.

## Next integration gate

The next native run must verify **whether the original queue producer and UART task make the request** from the serialized TPL input confirmed here. Remove the test caller's manual node creation and start/chunk/finish calls, and observe actual task context, transmitted bytes, and correlation record. The current source snapshot has existing transmit queue entries, so the first transmission must not automatically be treated as the test request; identify it by app/payload.

Then connect EUS/ATT/virtual controller input and the actual app service → display producer. The isolated TPL API is not reported as successful device input. Normal GAF service, natural main, full frame, and short UART response timeout remain incomplete. Overall 4/16=25.0%, API checklist 3/6, and the 16 acceptance conditions remain in force.
