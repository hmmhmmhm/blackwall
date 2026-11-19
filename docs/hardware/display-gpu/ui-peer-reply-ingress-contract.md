# Virtual peer reply and original UI producer contract

bw-0361, E05/E11/E13. **A contract was confirmed from the original display synchronization reply callback, one step above the existing API caller, to actual UI queue/ring.** These are isolated M7 tests across three originals, not evidence of completed virtual wire input, natural M55 app startup, or BLE authentication. Main/peripheral models were unchanged.

## Distinguishing upper paths

Direct call sites of the UI type 2 producer were found in original code. Original log strings and input accesses identify `SlaveDispalyCommandReplyListener` and `_MasterDisplayCmd_Listener` as inter-glasses display synchronization. Other direct sites include product-test-only and UART shell string handling. They were not selected as ordinary phone-app input, and product-test authorization was not forced on.

| Boundary | Stock 2.4 | Stock 2.3/Faceclaw38 |
| --- | --- | --- |
| UI type 2 producer | 445e74 | 445e18 |
| Master display reply callback | 4694e4 | 4695b4 |
| Master's UI call | 469608 | 4696d8 |
| Stop after UI producer return | 46960c | 4696dc |
| Slave display receive callback | 466358 | 466648 |
| Actual sync context slot | 200775d4 | 20077dc0 |

Master callback checks first reply byte at descriptor `+8`. For status 2 it requires previous request context at descriptor `+10`, and passes app-id at `+2`, length at `+6`, and payload at `+8` of the **existing transmit packet** pointed to by context `+8` to the UI producer. Remaining received reply bytes are not used as screen content. An arbitrary reply with no prior request is not a substitute for normal UI input.

Original initialization registers the slave callback as channel 2 listener. However, actual contexts in these three snapshots have only persistent listener channels 0/1/4 registered, and no master display reply callback among ten reply candidate records. Callback addresses, counts, table ranges, and original registration calls were bound together. Therefore directly injecting a display reply into current snapshots cannot be claimed normal reception. This does not deny registration at all other times/roles outside the snapshots.

## Executions verified

Connected to existing `probe_display_queue_producer.py --sync-ingress`, using existing pinned inputs/saved audits and actual UI queue, ring, and TCB unchanged. Callback descriptor, reply, and previous request are **synthetic inputs** declared in WORK. Tests covered app-id 10b length 0/4 and app-id 110 length 16, with request payload different from reply content. Other outgoing header fields are not verified by this callback, so this fixture is not called a valid on-air frame.

Execution starts at original callback entry and stops immediately after UI producer actually returns. Internal helpers are not skipped and returns are not set. Callback's final resource free/return is not executed, and synthetic WORK objects are not disguised as original heap objects to free them.

For each normal input:

- UI call arguments were exactly `[app-id, previous packet+8, length]`.
- Original queue API sent 12-byte `[2, app-id, length]` and changed receiver event-list state.
- Original queue receive removed the header and original ring reader read the exact previous-request payload.
- Full RAM/WORK/SCS/final register state matched between no-observation-hook and API-entry-observation runs. This is final-state comparison for this isolated input, not arbitrary observer noninterference or identical native scheduling.

Statuses 0/1/3/255 stopped before different original processing branches; status 2 without previous request stopped after original guard before diagnostic boundary. UI queue remained empty. Final returns of each error handler or safe handling of all malformed wire packets were not verified.

51 isolated runs across three originals (normal on/off, original queue/ring APIs, negative boundaries) were checked. Frozen probe/dependency rerun report was byte-identical. Existing activation 81 and display queue 72 also matched previous reports byte-for-byte. These are not added to product completion scores.

## Next actual input connection

Source-only tracing of stock 2.4 found the following; no new wire run at these addresses yet:

`SyncModuleReceivedDataHandler(468998) → byte-array feed(4b3a36) → byte parser(4b3a80) → callback dispatch(4b3884)`

Original byte parser calls dispatcher at 4b3c2a/4b3d2c; original feed call is 4689ec. Actual display-request queue consumer calls callback-registration/transmit API 4b4102 at 469c2a. This starts subsequent original parser/request-producer research; UART task name alone does not establish actual hardware transport.

Next execute the normal request producer to create a display wait, then pin frame format, CRC, correlation ID, and reply meaning of this byte-stream path. Actual transport registration and bus/IRQ input boundary also require separate binding. Do not copy the public phone BLE eight-byte header example into internal sync frames. Do not promote peer parser input or direct callback calls to natural peripheral input.

Normal GAF computation/full initialization remain separately unsupported and were not bypassed. E05/E09/E13 remain incomplete, overall 4/16=25%. No E11 touch success evidence was added.

## Reproduction and preservation

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/probe_display_queue_producer.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-private-output-folder> --sync-ingress
```

Combining with `--activation` is rejected. Existing outputs are not overwritten. Inputs outside Git and execution environment match existing display activation diagnosis. Private result is `simulator/ui-peer-reply-contract-04/report.json`, frozen `ui-peer-reply-frozen-02`, aggregate check `ui-peer-reply-research-01/manifest.json`.

The first negative boundary reused stock 2.4's default-branch offset on other versions and accessed unmapped memory beyond the intended boundary in old/CFW. Failures 01/02 and probe copies were preserved; actual branch target was decoded per original and corrected in 03. Firmware instructions/branches were unchanged. This is not reported as a general byte-parser failure. Zero new native runs, physical access, or persistent writes.

Two cases—new option output outside private path and conflicting options—were rejected before execution without creating output. Final 04 includes output-path guard and report is byte-identical to frozen 02. Existing API diagnosis, model, and natural boot completion state were unchanged.
