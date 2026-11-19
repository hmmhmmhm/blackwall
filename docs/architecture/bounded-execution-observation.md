# Bounded Observation of Original Execution Points

bw-0128. Execution-point observation was added to the stock 2.3/Faceclaw 38 comparison using the pinned bw122 profile. Existing CPU block/memory policy hooks were not replaced. Renode `CPU.AddHook`, already used for UART IRQ checks, records entry counts and order at explicit addresses. It does not write PC, registers, or memory.

The pinned g2flash cfw_patches.json base/output hashes were checked against the two existing original bundles, and changed ranges inside main compared with raw images. Thirty code points distinguished by the pinned recipe and instruction decoding are observed. Two pointer/connection-interval data locations are excluded. Twenty-two unique targets of new BL/B.W instructions in appended payload are also observed in CFW. Do not promote source descriptions into verified full function semantics. A reviewer identified and corrected documentation that said only initial BL/B.W instructions were observed.

Each patch site has an observation point at the same address in stock/CFW. Branch targets in appended CFW payload are observed only in CFW. Positive-control points are placed at main reset and the actual existing strict endpoint. Counts are retained per point and the event list is bounded to a fixed-size recent ring. R2 is read from events to compare argument values immediately before the next instruction at the heap-size patch reached in the first original observation. Full instruction traces, per-function equivalence, all-patch coverage, and chronological MMIO observation are outside this scope.

First, a small synthetic ARM guest tests AddHook counts/order, ring limits, and preservation of guest results. Then raw/main vectors, virtual models, selected existing strict endpoints, and observations for stock/CFW are compared again. If observation prevents execution from finishing within the host window, retain it as a failure. Existing model synthetic-state and unverified full boot/display/physical-device boundaries remain. Astra was not used.

Zero hits at fixed addresses do not prove copied or relocated code did not execute.

## Execution and verification results

The synthetic guest in `execution-observer-unit-01` confirmed reset 1/loop 3/store 1, two recent events/three dropped, guest result 42, and rejection of three invalid points. The first original observation `bounded-patch-observation-01` recorded one patch 14 entry on both sides. Based on this result, R2 observation immediately before the next instruction was added and register reading verified in unit02. Additional native execution checked this new register effect; it was not an unmotivated repeat of the same test.

Results in `private:simulator/bounded-patch-observation-02/report.json`:

| Item | Stock 2.3 | Faceclaw 38 |
| --- | --- | --- |
| Total observation points | 33 | 55 |
| Patch 14 entry at 0x48dae8 | 1 | 1 |
| R2 at next instruction 0x48daec | 0x2d000 (184320) | 0x2cc00 (183296) |
| Other 29 selected instruction patches | 0 hits at fixed addresses | 0 hits at fixed addresses |
| 22 appended-payload targets | Not installed in stock | 0 hits at fixed addresses |
| Reset/strict-endpoint controls | 1 each | 1 each |
| Final PC | 0x4e8394 | 0x4e8394 |

The R2 difference is 1024 bytes, observing the effect of the original MOVS.W modification. This does not prove successful TLSF allocation, validity of reserved memory, or normal Faceclaw BLE/display operation. The other 29/22 zero-hit results also concern fixed observation addresses. Source function names do not mean the entire feature was implemented or verified.

The two runs' main/bin and six unchanged inputs matched the frozen profile; strict.cs added only the observer after the same model. run.py added only observation setup and result output. Existing strict endpoints and selected UART/IOM counters all matched, with zero memory/system-policy violations apart from one guard. Actual main TX/ISR/I2C/CQ was zero; full boot/display remains incomplete.

Three host tests checked rejection of invalid observation records and generated-script syntax. An initially missing indent inside try was caught by host compilation before native startup and fixed. Neither this failure nor adding observation modified original instructions. A related summary is in `private:simulator/execution-observation-host-01`. A read-only independent review in the same GPT-6 family corrected observation-scope wording and raised no important issue about the R2 addition. Astra and a separate transcript-archive comparison were not used.

## Reproduction command

Use the existing research venv with Capstone installed and specify a new output directory.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/observe_native_profile.py \
  tests/profiles/bw122-iom-startup-mock0.json \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  "$HOME/Library/Application Support/Blackwall/simulator/bounded-patch-observation-new"
```

Earlier private original bundles, frozen profile assets, and pinned upstream source are required. Chronological MMIO event rings and full traces were not implemented in this tool.
