# TPL Service Input and Original Time-State Update

bw371, E13/E05. During bw370's next contract investigation, a message interpreted by the original app was found instead of transmission-only `app0b/01020304`. This covers **15 isolated ARM scenarios across three originals**, not actual ATT device input, scheduler replay, or completed natural main.

## Correction of transmission direction

The name `peer` in an existing root tool does not establish direction. The actual callback on the TPL header[7] bit-5=0 path puts `service(u32), length(u32), payload` into the `ble_msgrx` task queue and signals a task event. Queue/TCB pointers and actual TCB name were compared in SRAM. Do not interpret this as a function transmitting directly to the opposite temple. Old tool field names are retained for saved-report compatibility; this contract specifies their meaning as `tpl_local_callback`.

The original consumer removes a node from the queue and dispatches by service ID. 0x80 goes to the device-config protobuf handler. Existing 0x0b is not delivered to that handler by this switch; its node is freed. There remains no evidence that bw368 data transmission and bw366 display request automatically converge.

| Target | Local callback | Consumer | Service 80 handler | Time handler | Updated state |
| --- | --- | --- | --- | --- | --- |
| stock24 | 492e70 | 492bac | 505950 | 4faabe | 200076b4 |
| stock23 | 487094 | 486dd0 | 4e70d0 | 560c96 | 2000535c |
| Faceclaw38 | 487094 | 486dd0 | 4e70d0 | 560c96 | 2000535c |

Addresses are observations for pinned images, not common addresses for other candidates or physical devices. Functions were located through original signatures, actual switch BLs, and time-handler store/call instructions; behavior was not judged from log strings alone.

## Message candidate and independent expected values

The original service 0x80 log identifies command 0x80 as `eDevCfgCommandId_TIME_SYNC`. The original decoder consumes:

- Field 1 varint: command 128.
- Field 2 varint: message ID 1.
- **Field 128 length-delimited:** inner field 1 is time u32, field 2 is an auxiliary value read by the handler as a signed byte. Its units and physical-device meaning are not established.
- Payload for time 1700000000/auxiliary 16: `08800110018208080880e2cfaa061010`.

The pinned public even-g2-protocol schema calls the nested field 16, but `82 08` is actually field 128. This test executed the original decoder without generating code from the schema. The field-16 (`82 01`) control did not produce a decode error: **the ignored nested values remained zero**. The original time handler then stored 0/0 in state. Thus decode success or handler entry alone does not make a valid time message; this contract compares both desired state values.

The existing independent TPL encoder adds CRC to input and delivers with bit 5=0. Original TPL → registered callback → original allocator/queue executes, confirming all node bytes and count 0 → 1. The original consumer is then called in the same emulator memory, confirming count 1 → 0, original decoder and time handler, first five state bytes, and preservation of three neighboring bytes. The host does not create nodes or decode results.

The time handler stores decoded u32 and auxiliary byte in state, then calls the actual clock-application function. Two positive inputs 1700000000/16 and 1700000017/24 were reflected exactly in state and clock-call arguments. This is an intermediate assessment for the selected scenario, not complete app behavior through actual RTC application and final response/cleanup.

## Fifteen scenarios and incomplete boundary

Each image ran two normal inputs, one wrong nested field-16 control, one unhandled service-0b control, and one full-consumption attempt, totaling 15. First report 01 covers the first 12; report 02 adds the three full-consumption boundaries. The frozen-tool report matches source02 bytes.

After the state update, each full-consumption attempt stopped on the isolated fixture's unmapped **first read of RTC register 0x40004800**. No fake RTC value or helper stub was added. This is a scope boundary of the isolated fixture, not evidence that the actual main board lacks an RTC model. Next compare the original clock helper's device contract with the existing board model for possible reuse. Final consumer return, response, and natural task handling remain incomplete.

The same memory is used between the two API calls, but consumer SP/LR are set by an isolated-call fixture. Do not report this as natural consumption by the original `ble_msgrx` scheduler. Unicorn M-class is an auxiliary engine; zero new native M55 runs occurred. Executing TPL entry and consumer does not establish actual BLE/ATT connection success or successful bypass of GAF initialization.

## Next integration contract

This candidate is a starting point for **virtual phone → time-setting message → original app state/RTC application**. Roles and required responses for opposite temple/case and virtual-time limit for message completion were not yet pinned. The next order was:

1. Compare existing clock/RTC model and original application helper, and fix a terminal oracle for final consumption/response and cleanup. Do not duplicate an RTC model because of the isolated unmapped boundary.
2. Determine whether the task and controller input can be legitimately scheduled before natural main's GAF barrier. If not, switch to E05 normal service effects/completion.
3. Only if possible, connect connection-complete event → original CCB → ATT → EUS/TPL → this service → completed state in the same native run, including no-connection and wrong service/nested-field controls and reproduction across three originals.

Full E13 acceptance remains unchanged; this intermediate state update receives no completion points. Overall remains 4/16 = 25.0%, API checklist 3/6. There was no physical BLE/USB/UART, installation, persistent write, or external publication.

```sh
<private-python> tools/probe_tpl_service_ingress.py <simulator> <new-private-output>
```

Inputs bind bw368 capture files to the previous manifest and check main/SRAM hashes; the bw367 root report is also bound to its existing manifest hash. Results, frozen tool, and verification hashes are retained in `private:simulator/tpl-service-research-01/manifest.json`. Proprietary originals and SRAM remain outside Git.
