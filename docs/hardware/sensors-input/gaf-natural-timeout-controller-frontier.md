# Controller Version Query Blocking the Natural GAF Timeout

bw-0422. **The original's first GAF timeout return has not yet been reached.** A new run retaining protection and the 200,000-wait limit stopped beforehand at an unsupported virtual controller command. This identified a specific communications dependency that waiting longer cannot resolve.

## Actual execution

After original stock 2.4 ARM main reset → services/virtual connection → ATT time handling, the same machine ran for an additional **9.7464286 virtual seconds**. It performed original GAF request 2, trigger 1, and 11,059 busy queries, with 0 calculation completions and 0 calculation RAM generated. The final stop was PC `0x501676`, GPIO read `0x40010410` in `guard`; CFSR/HFSR and memory violations were 0. This is not evidence of full boot, normal sensor initialization, or real-device timing.

At the stop, execution was in the original `ble_wsf` task's Thread context. The buffer at R10=`0x20067c78` and actual SRAM contained `01 01 10 00`, with R8 length 4: H4 command type 1, little-endian opcode `0x1001`, and argument length 0. It was blocked on the RDY query before transmission, with only the existing 59 startup commands and 3 runtime events processed. The model was not changed based on speculation that this was an RSSI request.

[Bluetooth Core HCI specification §7.4.1](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html) defines OGF 4/OCF 1 as Read Local Version Information. It takes no command arguments and returns status, HCI/LMP versions, each subversion, and company identifier in Command Complete. The specification establishes frame format, not the actual G2 controller version values. The request's original producer, scheduling purpose, and subsequent required commands remain unknown.

## Change and observation scope

The existing bw399 pinned scoped observer input was reused. The [bw421](../../firmware/main-read-routing-pilot.md) read-routing candidate was not adopted; production memory policy `29daafce…` with full-page routing and write/execute protection remains. The cache helper was replaced with verified `5564e889…`. Original main, branches, returns, timeout iteration count, and TCB/SP were not modified.

An observation hook was installed at setter continuation `0x55496e` after the first service helper actually returns. Original BL and request arguments 2/4 were verified by disassembly. The original wait follows a 200,000-iteration path decrementing 1,000,000 by 5. Host limit 1,500 seconds and virtual 300,000 ms are finite observation budgets, not replacements for the firmware timeout. This run stopped strictly before either limit; the continuation hook was not hit.

| Material | Finding |
| --- | --- |
| native-01 | After additional original execution: 11,059 queries and GPIO guard. Timeout not observed; scenario false |
| native-02 | EOL error generating a progress-log string caused failure before run.py execution; excluded from ARM success evidence |
| native-03 | Same boundary reproduced after Python syntax precheck, with registers and buffer collected after stop |

Existing runtime JSON values and four SRAM snapshots (initial, connection, ATT, final) are exact between native-01/03. This establishes agreement within the observation scope of added register collection, not a general guarantee that observers have no effect. native-01's progress log was preserved with escaped newlines; actual newlines are used from native-03. Failed material was not overwritten.

## Audit and next work

`verify_gaf_timeout_frontier.py` performs 19 checks, comparing original hash, original loop literal, input hash and byte-identical regeneration, logs, SRAM, task/buffer provenance, exact opcode, guard, and zero calculations. Input manifest JSON values match, though key ordering by process can differ at the byte level. The initial failed byte-exact manifest expectation is not treated as an original code difference. Two counterexamples were rejected: forged timeout return and SRAM/buffer changed together to another opcode.

Next is a **0x1001 request/response contract using an explicit virtual controller identity**. Do not assume actual controller values are known or unconditionally ACK other HCI commands. First check exact command, response length/fields, byte/fragment handling, RDY/IRQ, completion state, and invalid input. Resume the same original timeout path after closing this communications dependency. Do not generate normal GAF ready or derived RAM to advance it.

Private material is in `gaf-natural-timeout-native-01/02/03` and `gaf-natural-timeout-research-01`. Execution/saved-audit tools are `probe_gaf_natural_timeout.py` and `verify_gaf_timeout_frontier.py`. E05/E06 and overall 8/16=50.0%, display checklist 3/6 remain unchanged. No real-device access, writes, Astra/subagents, or external publication occurred.
