# Ring reception and runtime duplicate suppression across three originals

bw-0456 · E11 partially complete. Stock 2.4, stock 2.3, and Faceclaw38 each confirmed virtual UART0 ring relay → actual original ring task → source 4/code 1 delivery → return to original caller. In stock 2.4, a second UART report was actually received and classified but not delivered again due to the original's 100-tick duplicate suppression. App/UI consumption, display output, and direct R1 BLE remain unverified; overall acceptance is 10/16=62.5%.

## Natural reception in three originals

The 30-byte frame and source contract from [bw455 input contract](ring-input-ingress-contract.md) were used unchanged. The stock 2.4 single run reused saved material; only stock 2.3 and Faceclaw were newly run. Addresses come from the source contract that checks pinned raw SHA and original service 90 callback, BL, and queue wrapper.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| Ring receiver | `0x4eeec0` | `0x47911a` |
| Return to original caller | `0x4ef2be` | `0x479518` |
| Delivery arguments R0–3 | `[4,1,0,0]` | Same |
| Current linked task | ring / priority 46 | Same |
| UART exception 31 increase | 3 | 3 each |

For both older versions, actual relay callback → kind 2 queue wrapper → ring receiver was also observed. Relay R1 report pointer/R2 length 11 passed to wrapper R0/R1. This is evidence of actual execution of the registration/queue path found in source. Faceclaw entered actual `0x7d5800` hook and `0x7d5812` fallback. The external 24-byte frame before fallback and original SP/TCB restoration at the final caller were confirmed. Do not expand this into verification of the lease-held path.

Device models across all three runs were byte-identical; version-specific vendor startup fixture differences remain. Audits covered complete SRAM, R0–15, and virtual time before/after injection; actual 30-byte read/pending 0; source tick 1000 update; Thread context; fault/memory/17 guards/overflow 0; and process removed. All 60 family audit checks passed.

## Natural suppression of a second report

A new stock 2.4 run stopped at the actual caller of the first report at tick 1000. With original execution state retained, a second report at tick 1099 was supplied under new UART request ID `0x9011`. The host did not write the last ring tick or change the original duplicate-check branch.

Both 30-byte frames were actually read, consuming 60 bytes total. Relay, queue wrapper, and receiver each ran twice. Only the first report delivered `[4,1,0,0]` through slider; the second returned normally with R0=0. Last tick retained 1000 written by the original first run, and final caller R2=99 matched the source's unsigned difference. This distinguishes suppression from a second report never being received.

Both injections preserved CPU, SRAM, and time. The second report also traversed actual UART exception 31, with pending 0, linked ring task, SP/TCB and Thread return, and fault/guard 0 confirmed. The first report's source trace and complete SRAM exactly matched the previous bw455 single run. This is a control over the added observation range, not universal neutrality of all hooks. All 27 duplicate audit checks passed.

Pausing then resuming at the first caller records its same-PC hook once more. This is not counted as a third receiver return. The new stop observer stopped at the caller only after the actual second receiver entry; receiver ran exactly twice. At second input only UART pending changed 0→30, while original tick did not change.

## Preservation and next boundary

There were three new M55 runs (two older versions and one duplicate); the stock 2.4 single run was reused. Unit/standalone ARM tests were unchanged and not rerun. No further device model changes, physical device, subagent, or external publication occurred. Runs and audits remain outside Git in `simulator/ring-native-families-research-01/`, `ring-families-native-01/{stock23,cfw}`, and `ring-duplicate-native-01/stock24`, pinned by `simulator/ring-native-families-manifest.json`.

Next, connect a virtual peer to respond to the actual `0x108` request produced by ring input and verify consumption in the original app and idle/UI paths. Distinguish successful input delivery from UI state change and pixel generation; normal GAF and natural rendering dependencies remain. Integrate into the public scenario after confirming this consumption contract.
