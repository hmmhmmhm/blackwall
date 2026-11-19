# HCI Reset virtual peer and natural main exchange

bw-0285. Implemented without physical device access. Overall completion is 13/29=44.8%. Transmission and reception of the third command were confirmed in natural mains of stock 2.4, stock 2.3, and Faceclaw38. The first stock 2.4 observation was retained incomplete as described below; after verifying bw286 tool changes, remaining verification was completed in a separate capture under a new execution contract. Full boot and integrated display remain incomplete.

## Explicitly selected virtual response

`applicationReset`, default false, was added to the peer in `renode-em9305-reset.cs`. It is allowed only with a successful explicit version scenario. After the existing two commands it accepts exactly `01 03 0c 00` as the third and replies `04 0e 04 01 03 0c 00`. This is a virtual fixture, not execution or measurement of physical EM9305.

Command acceptance and response consumption wait until CS rising, not merely IOM payload completion. Mismatched payload and invalid receive length are rejected before state changes. A fourth command is unsupported, and repeated reset does not automatically rearm the scenario.

The original application GPIO consumer receives only:

- After second response consumption: idle-low.
- After complete actual Reset command acceptance, while response pending: ready-high.
- After third response consumption: idle-low.
- At original reply-drain PC: low only after third response consumption completes.

CS high, exact PC/address/pad configuration/R0, and reset-released conditions remain. New drain PCs are 2.4 `4dd240` and older versions `4c99fc`; default 0 disables it. Original ARM branches/returns were not changed and main initialization checks were not bypassed.

## Verification results

The red log where platform load failed because the constructor lacked a drain argument was retained. After implementation, 59 conditions passed at default capacity; the final two-byte-split scenario, strengthened for incorrect first payload byte rejection and constructor constraints, passed 114. Do not add these counts as separate independent feature counts. Reflection tests explicitly set the added optional argument false to preserve prior semantics.

Stock 2.3 and Faceclaw38 showed from original reset:

| Item | Result |
| --- | --- |
| Accepted commands / consumed replies | 3 / 3 |
| CS frames / IOM commands | 7 / 14 |
| New application GPIO polls / drain polls | 4 / 1 |
| First five TX descriptor words | `520,260,260,2080,260` |
| Next record | Length 10, opcode `fc43`, parameter length 6 |
| Next unsupported boundary | Original write-ready `549fce`, GPIO `40010410` read 4 |

R8=10, R9=0, R10=next actual packet pointer and SRAM record were compared. The previous Reset record was consumed and the original upper handler prepared the next command; that command itself was not transmitted. Unlike bw284 synthetic function calls, these results came from natural main execution. They do not verify actual controller, physical IRQ, or full BLE initialization.

Default-off stock 2.3 control exactly matched previous observed CPU and selected events: command/reply 2/2, frame 5, and zero new drain polls.

Subsequent stock 2.4 also showed command/reply 3/3, frame 7, IOM 14, GPIO 4/drain 1, the same first five descriptor words, and a next record of length 10/opcode `fc43`. Next unsupported write-ready PC is `501676`. Original R8/R9/R10 and SRAM packet were compared with the same checker. Actual exchange in all three images was with a virtual controller.

## Incomplete stock 2.4 observation

The first run's inherited runtime had a 45-second host observation limit. The last live sample was 57,563,000 instructions, PC `494f4a`, before HCI initialization. The earlier successful bw283 run reached 65,895,166 instructions at its 25-second sample, so host seconds alone do not guarantee equal guest progress. These numbers do not establish firmware performance or model regression.

There was no guest strict stop when 45 seconds ended. The post-stop SRAM exporter refused to save, so no unique CPU report was generated; the host paused and terminated it. Guest failure was not proved. Input, log, and live-sample hashes were retained in `failure.json`; the run was not relabeled success or software error, nor restarted.

At that point the next task was separating observation limits from native-child lifecycle and evidence collection, then separately planning remaining stock 2.4 integration verification. Do not automatically rerun merely because observation expired or overwrite existing failure logs.

The preceding paragraph reflects the point when the first run was deferred. Bw286 implemented the [execution lifetime contract](../../architecture/native-observation-lifetime.md) and verified host 25, fixed 25, and actual M55 off control with exact CPU/instruction/event results. Subsequently `application-hci-reset-guest-stop-candidate.json` specified a new execution contract and `application-hci-reset-main-02/stock24` verified it. The earlier plan and incomplete capture were unchanged. This was a new plan following verified tool changes, not an automatic retry with only a longer timeout.

## Preserved material

Simulator directory outside Git:

- `application-hci-reset-red-01`, `application-hci-reset-unit-02`, `application-hci-reset-legacy-01`: red, final 114, existing 58 conditions.
- `application-hci-reset-main-01/{stock23,cfw}`: semantic contract passed.
- `application-hci-reset-main-01/stock24/failure.json`: incomplete observation and actual log hashes.
- `application-hci-reset-control-01/stock23`: default-off control.
- `application-hci-reset-saved-audit-01`: audits of three saved runs.
- `application-hci-reset-contract-01`, `-02`: identical saved SRAM/packet/ring/write-context analysis.
- `application-hci-reset-verification-01/manifest.json`: pins Python 29, models 4, unit, source 54, native, and audit SHAs. IOM/keyDB/marker and web gate are unchanged.
- `application-hci-reset-main-02/stock24`, `application-hci-reset-saved-audit-02/stock24`: successful stock 2.4 capture and saved audit under the new execution contract.
- `application-hci-reset-complete-contract-01`, `-02` and `application-hci-reset-verification-02/manifest.json`: integrated evidence for three images and off control, and identical pinned reanalysis with Python 29. Default checker options produce a byte-identical report to past analysis; the new 2.4 capture is included only by explicit completion option.

Next verify original generation, parameters, and response-consumption contract for opcode `fc43`. Do not add an arbitrary success response before confirming meaning and side effects. Through this path, connect natural app loop/display initialization and already verified glyph/GPU calls.

The hardware authorization boundary for installation/recovery remains. This test included no glasses scan, connection, OTA, MRAM write, or bootloader installation.
