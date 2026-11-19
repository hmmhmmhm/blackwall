# Repeated touch execution contract across three originals

bw-0454 · E11 partial. Stock 2.4, stock 2.3, and Faceclaw38 all started from original main reset and handled two independent GPIO27 inputs through original IRQ, touch task, slider dispatch, and caller return. Stock 2.4 reused bw453 saved execution; only the two older versions ran newly. This is not evidence of physical devices, second UI consumption, screen output, or ring success. Overall acceptance is 10/16=62.5%.

## Common scenario

Explicitly enable the default-off adapter from [repeated report lifetime](touch-repeat-frame-lifecycle.md). Deliver first report `020800003412cdab0180ffff5ac317e9` via a 1 ms low/high GPIO27 pulse. After confirming actual caller return, complete consumption, and IOM quiescence, load next report `02400aa73412cdab0180ffff5ac317e9` and send a separate pulse. Peer loading does not set CPU branches, returns, TCB, SRAM, or readiness. Original code consumes each report through pointer03 → four 4-byte reads.

| Item | Stock 2.4 | Stock 2.3 | Faceclaw38 |
| --- | --- | --- | --- |
| Original handler | `0x4fd75c` | `0x51c074` | `0x51c074` |
| Actual caller return | `0x5053b4` | `0x52f358` | `0x52f358` |
| First slider arguments | `[1,1,0,0]` | Same | Same |
| Next slider arguments | `[1,4,10,167]` | Same | Same |
| Reports / chunks / reloads | 2 / 8 / 1 | Same | Same |
| Falling edges / IRQs | 2 / 2 | Same | Same |

Caller was found from actual LR in prior original execution, and corresponding BL in each pinned raw image was redisassembled to verify it calls the handler. Version addresses were not derived by uniform subtraction. First and second handler SP/TCB match at caller return in Thread context. Both IRQ entries are exception 72, IRQ56.

`strict.cs` is byte-identical across three boards. Stock 2.3/Faceclaw boards differ by one byte in existing version-specific `vendorStartupHex` fixture, so full board byte identity is not claimed. That fixture was not changed for new repeat-input behavior. Time is a fixed 10 MIPS virtual profile; version processing differences are not interpreted as physical performance.

## Verification and preservation

Saved audit passed 72 checks: raw hashes, actual original BL, two handlers/callers and SP/TCB/Thread context, distinct reports/slider arguments, GPIO/IRQ counts, SRAM/R0–15/virtual time before and after reload, SRAM before and after first GPIO input, release/pending, strict guards, CFSR/HFSR, memory, and trace overflow. Two new runner exits were 0 and owned processes removed. No new device model changes or unit reruns; bw453 red/green 86 and default 59 controls were reused.

A bw453 post-export summary print queried a stale key; only host summary output in the new runner was corrected. Runtime, observations, model, and scenario behavior remained unchanged. Prior runner and results were not overwritten. Faceclaw observations here are limited to original touch handler; no new claim of CFW wake hook or app-delivery branch verification. Hook fallback evidence is separate in [bw452](touch-wake-family-contract.md).

Runner, plan, verifier, and audit are outside Git in `simulator/touch-repeat-families-research-01/`; original, board, run logs, SRAM, and trace for new images are in `touch-repeat-families-native-01/{stock23,cfw}`. `simulator/touch-repeat-families-manifest.json` includes reused stock 2.4 material and this snapshot.

## Remaining integration scope

Second-input application consumption/UI change, ring and remaining supported gestures, post-reset input lifetime, natural main screen, and continuous frames remain incomplete. Next tool work connects this verified input boundary to reproducible public-runner scenarios. New candidates must also have source profile/address verification, without forced branches or implicit private research-folder dependence. The screen separately requires normal GAF computation and natural-render dependencies. Current evidence does not complete or reduce E11 scope.
