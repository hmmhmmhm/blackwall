# M55 board diagnostic of original sync transmission and CRC error

bw-0363, E05/E13/E14. **Stock 2.4, stock 2.3, and Faceclaw38 confirmed original sync transmission API return, actual UART0 DMA bytes, and IRQ handling.** On the same board, header CRC error diagnosis also passed TIMER14 and returned to the receive API. This is not natural app startup of original main or completion of UART0 RX device input.

## Execution boundary and reuse

The pinned Renode M55 board, inputs, normal hold, memory policy, and copy bootstrap from the [existing activation diagnostic](../display-gpu/display-activation-native-diagnostic.md) were reused. Original main runs from reset and normally pauses the entire machine at IMU getter entry. Then an explicit API test caller is copied into emulated ITCM via guest memcpy. Source checks, current input hashes, and unchanged existing model/original bytes are verified.

The caller invokes original allocator and sync start/chunk/finish APIs in the original Sensor Thread/PSP context. The host does not set UI/Display PC, TCB, stack, or mode. Initial PRIMASK/BASEPRI/IPSR 0 and return to original stack were confirmed. The caller contains no CPSID/CPSIE/MSR and does not replace original internal helpers, branches, or returns. This remains an API test replacing first entry with a test caller.

Peripheral C# models were unchanged. Existing `BlackwallUartDmaTx` untimed completion and UART0 IRQ, and existing TIMER14, are used. The model's immediate DMA completion is not interpreted as physical transmission time or a performance measurement.

## Transmission evidence

The original allocator creates the request node/packet and original API creates ID, waiting record, and frame. The original finish transport leaf actually executes. Original UART0 DMA driver configures registers, and the existing model retains bytes read from guest SRAM in its transfer record. The CPU enters the actual UART0 exception, executes the original handler, returns to the original Sensor task, and continues to the caller's end.

| Input | Additional DMA frame | Completion increase | UART IRQ exception increase | Original task/stack return |
| --- | ---: | ---: | ---: | --- |
| Stock 2.4 | 1 | 1 | 1 | Confirmed |
| Stock 2.3 | 1 | 1 | 1 | Confirmed |
| Faceclaw38 | 1 | 1 | 1 | Confirmed |

The declared request's eight-byte header for app 10b and length 0 is the payload. An independent CRC encoder computed from the generated ID read from the actual descriptor matched the entire DMA record. The three pinned scenarios' frame was `01800a00080002029700010b01000000007b2c`. ID 800a is not hard-coded as a constant for all devices or new candidates.

Original main/model/initial SRAM and ITCM inputs matched baseline. CFSR/HFSR/memory-policy violations and unsupported peripheral accesses were 0. This verification is limited to the API diagnostic for the three pinned profiles used.

## CRC error return

`bad-header-crc` normally pauses immediately after transmission and prepares a reply frame corresponding to the actual ID in WORK. One header CRC bit is altered. The same caller continues and calls original `SyncModuleReceivedDataHandler`; the host does not reset PC, TCB, or IRQ mask in the second stage.

The original CRC error branch was entered once, then the receive API returned to the original caller through TIMER14 diagnosis, which was unmapped in standalone M7. Parser state returned to 0, UI queue was empty, and existing display reply record preserved. All three images passed the same decision. The decision checked error branch, exact input bytes, parser/record/queue, CPU fault, and original task/stack together, not only a caller-completed marker.

This is complete evidence for **incorrect header CRC handling**. Payload CRC, unknown ID, duplicate reply, timeout cleanup, and complete reconnection are not marked complete. It also did not insert a subsequent normal frame to verify recovery via the actual RX task.

## Results and saved audit

Three send cases have 15 judgments each and three CRC cases 21 each, totaling 108. Schema 2 semantic contracts distinguish execution captures from semantic verification. Input and capture files are hash-pinned and a single raw-log result is checked against exported JSON. Saved audits use separate output paths and do not rerun firmware.

- Six normal native captures and six saved audits passed.
- The frozen auditor's stock24 CRC saved-audit report exactly matches the current auditor result.
- Three input/export/log tampering cases and three CLI path/option/case mistakes were rejected.
- Separate synthetic result fixtures changed DMA payload, IRQ count, and task owner. Even after file consistency was restored, semantic verification failed in all three cases. These are verifier negative controls, not actual firmware failures.

Initial source preparation failed due to a missing parent output directory; no native execution occurred. Two subsequent host setups exited before API calls due to the incorrect assumption that DMA was a separate Machine node. Failures were retained, and actual source/saved native diagnosis established the `guard.Uarts[0].DmaTx` object graph and corrected it. The same node-name guess was not repeatedly tried.

Private capture pins mark `import-after-original-verification` because they were imported at the current time after those runs had already been verified. They are not recorded as created in the past. Future runners create pins directly after execution.

## Reproduction

Existing pinned assets, Docker image, LLVM, and venv-02 are required. There is no device connection.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/run_sync_transport_m55.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-private-capture> --case stock24 --scenario send
```

Other baselines are `stock23`/`cfw`; error control is `--scenario bad-header-crc`. Saved audit explicitly specifies the same case/scenario.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/run_sync_transport_m55.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <existing-private-capture> --case stock24 --scenario bad-header-crc \
  --audit-existing --audit-output <new-private-audit>
```

Normal captures are `simulator/sync-uart0-native-03/{stock24,stock23,cfw}` and CRC captures `sync-uart0-crc-native-01/{stock24,stock23,cfw}`. Combined manifest, freeze, and failure causes are in `sync-uart0-native-research-01`.

## Remaining integration

Received bytes are still passed to the original receive API by the test caller. Next connect UART0 RX FIFO, cause IRQ, and receive task/callback registration to the original, injecting virtual opposite-temple bytes at the device boundary. Use of a PL011 backend alone does not establish that the current adapter already supports RX injection and IRQ delivery.

E05 normal required initialization/app events, E13 actual virtual transport→task→app, and E14 complete failure scenarios remain incomplete. GAF calculation, natural UI, and full boot status are unchanged. Overall 4/16=25% remains. No physical UART/BLE access, flashing, or persistent write occurred.
