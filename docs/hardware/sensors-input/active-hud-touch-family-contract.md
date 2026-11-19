# Additional Touch and Screen Scrolling Across Three Original Families

bw-0487. **Stock 2.4, stock 2.3, and Faceclaw38 all showed additional touch → original UI command handling and return → screen scrolling.** Each original's no-input control retained screen and input tick over the same 200 ms. E11 is partially complete because the ring's subsequent UI effect remains; overall progress is **14/16=87.5%**.

The [bw486 input/no-input evidence](active-hud-ui-consumer-contract.md) for stock 2.4 was reused, and the two older families each had one new input and one no-input run. Four new native runs start at original main reset. After initial touch wake, first screen, and a 400 ms stabilization period, a second scroll is delivered at the GPIO27/IOM5 boundary. Virtual peer UART responses 8/4 use contracts checked against actual generation and consumption code in each original.

## Source verification by version

Additional peer contracts are not copied between originals without checking versions. Along with main SHA, the runner verifies and records six instructions for response 4 generation, command producer call, UI queue type 3, response 8 check and UI7 delivery, and actual app1 command handler call.

| Original | app1 callback | Command handler | Callback cleanup point | Cleanup SP relative to entry |
| --- | --- | --- | --- | ---: |
| Stock 2.4 | `0x4b7a58` | `0x53186c` | `0x4b7cca` | −128 bytes |
| Stock 2.3 | `0x4ad7e4` | `0x500e1c` | `0x4ada44` | −120 bytes |
| Faceclaw38 | `0x4ad7e4` | `0x500e1c` | `0x4ada44` | −120 bytes |

The callback cleanup observation point is immediately before original stack restoration. It is not confused with SP after function return. The audit checks that execution actually reaches it after the original handler and retains the same UI TCB/Thread mode and command pointer/length. Applying 2.4's 128 bytes to the two older families is rejected. The host did not set PC, TCB, branches, return values, or guest SRAM.

## Results

| Original | Completed frame in input run | Input screen change | 40 no-input samples | Six initial boot SRAM snapshots |
| --- | --- | ---: | --- | --- |
| Stock 2.4 | 13→18 | 3,790 pixels | Unchanged | Existing bw486 evidence |
| Stock 2.3 | 13→18 | 3,790 pixels | Unchanged | Exact against E06 pinned baseline |
| Faceclaw38 | 13→18 | 3,790 pixels | Unchanged | Exact against E06 pinned baseline |

Starting raw frames are byte-exact across all three originals, as are final raw frames after scrolling. Changes caused only by elapsed time or fading are not accepted. Each input/no-input pair uses the same main/model/board/activation/run/runner and identical profiles except mode. Registers, instruction count, virtual time, and SRAM were preserved before and after injection. The 250 µs waveform and 200 ms observation period are declared virtual inputs, not measurements of physical latency/FPS.

Existing cold sensor service and reference GPU functional model remain. All three originals scroll the same basic HUD path. This does not claim equivalence of Faceclaw-specific screens or all CFW features. Physical display, sensor mathematics, and full GPU ISA are outside verification scope.

## Independent audit and preservation

The existing case option in `run_active_hud_input.py` was extended. The same peer contract is used after source verification for each original. `audit_active_hud_input_pair.py` distinguishes per-original SHA and stack contracts and compares actual source bytes. The historical bw486 audit remains preserved with its saved source and is not rebuilt with the current builder.

The two older pairs were independently run from `/tmp` with an empty PYTHONPATH using only copied audit source; each was byte-exact with its normal report. Existing 2.4 material also passed the current generalized audit. Four semantic negatives for incorrect per-original stack and a different UI task were rejected; the integrated audit also rejected a failed or missing case. Checks used saved material without new guest execution.

All four owned containers were removed and their absence confirmed in the actual Docker list. Source, plans, main, frames, SRAM, logs, audits, and partial-failure rejection results are pinned in a private manifest. No physical access, flash/OTA/MRAM writes, subagents, or GitHub publication occurred.

Next, connect original consumption of the existing v1 ring scenario through actual UI return and screen effect. Natural task consumption of sensor samples, E12, is a separate subsequent acceptance condition.

Private material: `simulator/active-hud-touch-family-native-01`, `active-hud-touch-family-pair-audit-01`, `active-hud-touch-family-frozen-audit-01`, `active-hud-touch-family-compat-audit-01`, `active-hud-touch-family-research-01`, `active-hud-touch-family-acceptance-01`, `active-hud-touch-family-manifest.json`.
