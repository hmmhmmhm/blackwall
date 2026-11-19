# Original UART Task Request and Transmission from Serial TPL Input

bw368, E05/E13/E14. On actual M55 boards for three originals, **TPL input → original SendDataToBoth → transmit queue/event → original uart_sync_thread → request ID, correlation record, and DMA frame** were connected. The TPL caller then returned to the original Sensor task/stack. Test code does not create nodes/descriptors or directly call allocator/start/chunk/finish. Initial TPL input remains an API diagnostic, not successful BLE/ATT device input.

## Input and original execution

The existing main reset → normal getter hold → verified memcpy/ITCM caller recipe was reused. Host seeds are limited to previously permitted r0/r1/r2/LR/PC; SP, TCB, and IRQ masks are unchanged. Main, initial SRAM/ITCM, strict device model, and board match the existing baseline. Additional C# is a pinned observer, not a receive model. It only reads guest memory and calls Machine.Pause at declared points; it creates no guest state. Observer noninterference was not proven.

The input is the single TPL frame in the [bw367 contract](../hardware/display-gpu/display-request-root-contract.md): transport 0, app 0b, payload 01020304. Faceclaw executed from actual 7d2638 hook through original TPL fallback for normal input. The test caller invokes only three functions: TPL entry/hook, original queue creation, and original queue get. Harness assembly call targets and original queue-creation signature were checked separately. Bootstrap PRIMASK/BASEPRI/IPSR=0 was confirmed.

The original producer creates a heap node and 0901 data packet, and the original UART task executes start/chunk/finish. Because other requests may be queued, app, length, and payload are compared in the node/packet at original start entry to select only the target request. The first transmission or a fixed ID alone is not counted as success. The original descriptor contains channel 1, length 12, original heap packet/node, and TPL completion callback; the reply callback is the MasterData callback found in the original kind-1 branch literal.

The observed frame was the same across all three images:

`01800a000c0001c29601090b0000000400010203043102`

The ID in this run is 800a, but is not assumed constant. An independent sync CRC encoder uses the actual descriptor ID and payload and is compared with all bytes read by DMA. A pending record and reply callback for that ID were checked. Peer response, record cleanup, and subsequent execution of the TPL completion callback remain unverified.

## Natural preemption and caller return

The first run 01 failed only input-return among 22 checks including UART transmit, ID, and frame. In fact SendDataToBoth woke the UART task, which preempted TPL before it returned. The assumption that the input mailbox had to be filled first was withdrawn and the failure retained. A terminated process was not described as resumed; two observation points were declared in new run 02.

1. Pause at the original finish-call return point for the selected request. Observe descriptor/packet and original UART task, SP, and xPSR.
2. Resume the machine without reseeding host registers. Pause when the scheduler returns to the original TPL caller and it records TPL return 0 and a marker. Confirm original Sensor TCB, entry SP, and Thread mode.

Point order is not forced; PC/TCB/SP are bound separately at each point. Actual run 02 had transmission completion → input-caller return. The first pause's descriptor is retained in the observer's separate copy, distinguishing it from later UART-loop stack reuse. The input caller's API diagnostic does not mean natural main initialization completed.

## Results and verification

| Target | New native 02 | Current saved semantic audit |
| --- | --- | --- |
| stock24 | 23 checks passed | 27 checks passed |
| stock23 | 23 checks passed | 27 checks passed |
| Faceclaw38 | 23 checks passed | 27 checks passed |

Additional saved checks cover absence of manual request APIs, both phases' PC/TCB/SP, actual heap node/packet, and descriptor channel/length. Original UART task/stack, pending callback, DMA payload/completion, UART0 IRQ31, zero CPU faults, zero unsupported accesses, and unchanged original/model were also confirmed. UI queue is 0: this scenario is a data request, not display activation.

Three synthetic negatives modifying producer app, request TCB, or DMA payload while consistently changing JSON/log/capture hashes were rejected by respective semantic checks. These are checker negatives, not new ARM runs. Saved audits of 12 past TX/CRC/RX/JBD native runs comprising 270 checks also passed under the current checker. The same firmware was not run 12 more times. A separate saved audit retains that first failure 01 did not meet current two-phase requirements either.

## Reproduction and pinned material

```sh
<private-python> tools/run_sync_transport_m55.py <simulator> <new-output> \
  --case stock24 --scenario tpl-request-send
<private-python> tools/run_sync_transport_m55.py <simulator> <existing-output> \
  --case stock24 --scenario tpl-request-send \
  --audit-existing --audit-output <new-audit>
```

The implementation uses an optional scenario in the existing runner, the sync_root_native helper, and a pinned root observer. Input/capture pins, JSON/log consistency, schema 2, and saved audits under the current model remain. Historical capture audits do not call the new builder. Source reports, exact harness/runtime/model/main hashes, failures, and frozen runner are linked in `private:simulator/tpl-request-research-01/manifest.json`. Proprietary images/SRAM remain outside Git.

## Remaining integration boundaries

Manual request structures and direct start/chunk/finish calls were removed. However, original GATT/ATT input was not delivered from an actual virtual device. Next are connecting EUS callback registration/callers and actual receive queue/virtual controller input, and the path by which app data becomes a display request through a service handler. Do not assume EUS security/connection/handle conditions pass without checking them.

Normal GAF service, natural main app, full 576×288 frame, short-frame timeout, and peer-response cleanup/disconnect/delay remain. Acceptance criteria and denominator 16, overall 4/16 = 25.0%, and API checklist 3/6 remain unchanged. No physical BLE/USB/UART, firmware installation, persistent write, or external publication occurred.
