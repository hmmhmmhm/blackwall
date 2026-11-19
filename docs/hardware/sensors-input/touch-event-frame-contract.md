# Touch and wear-state 16-byte frame consumption contract

bw440. From the existing register 03, 16-byte read stop, **original consumer frame interpretation, branches, and input-dispatch arguments** were confirmed. These are 153 isolated ARM scenarios executing original handler, read helper, and actual memcpy/memset from stock 2.4/2.3/Faceclaw38. Bus callback, system query, and external-dispatch leaves are explicit ABI substitutions; actual Renode task/IRQ and UI change remain unverified. E11 remains partial; overall 10/16=62.5%.

## Original functions and input structure

| Item | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| Consumer | `0x4fd75c` | `0x51c074` |
| 16-byte read helper | `0x4fbd7e` | `0x57961e` |

The callback was obtained from actual context RAM/function pointers per image. Only one register 3, length 16 request was handled by ABI. Helper and buffer copy use original instructions, and original branches executed from handler through return. Reset events stopped immediately before hardware reset helper entry. Original code bytes are read-only and were checked identical after execution.

| Offset | Consumption meaning and evidence |
| --- | --- |
| 0 | proximity enum: 0=`PROXIMITY_NONE`, 1=`PROXIMITY_UNWEAR`, 2=`PROXIMITY_WEAR`, confirmed by original strings and SRAM pointer table. Values ≥3 discarded before subsequent processing |
| 1 | slider event mask |
| 2 | diffX; actual dispatch argument passed with `uxtb` |
| 3 | speed; actual dispatch argument passed with `uxtb` |
| 4/6/8/10 | little-endian 16-bit bsln / kv_bsln / raw / diff, confirmed by original log format and nonzero input |
| 12..15 | copied as part of 16 bytes by read helper, but meaning not consumed in this handler |

Do not infer the first proximity byte as a contact count. Initial research-script names `count` and dispatch list `contact` were respectively the proximity raw value and type 3 notification. These were corrected in `annotated-report.json` and semantic audit. Physical generation of controller payload, electrical polarity, and sampling delay are unverified.

If proximity is nonzero and differs from previous value, the stored byte updates and a type 3/new-value notification is attempted. Zero does not clear the previous stored value, and repeated identical nonzero input creates no duplicate notification. Read callback error or proximity ≥3 prevents slider processing and storage update.

## Slider dispatch in normal mode

Numbers below are original dispatch function codes, not expanded into user gesture names or UI behavior. First argument is a separate query's 0/1 result, not a physical left/right measurement.

| Mask bit | Dispatch code / data arguments |
| --- | --- |
| `0x01` | 13 / 0,0. Two separate external calls also exist |
| `0x04` | diffX<2: 0 / 0,0; diffX≥10: `0x1010` / 0,0; 2..9: no dispatch |
| `0x08` | 1 / 0,0 |
| `0x10` | diffX=2: 17, otherwise 3 / 0,0 |
| `0x20` | 5 / diffX,speed |
| `0x40` | 4 / diffX,speed |
| `0x02` | 14 / 0,0, checked after the above |
| `0x80` | Branch to reset-helper boundary and skip other normal slider dispatch |

If the separate mode query is 1, flags/diffX are passed to another consumer instead of normal mask dispatch. Normal mode 0, alternate mode 1, and role 0/1 are explicit synthetic fixtures. Logging level and raw-dump flag are also fixed to 0. This query substitution is not evidence of actual main state or integrated success forced through a branch.

## Execution and audit

51 scenarios per image include 0/each single bit/composite 127/reset 128 and 255, diffX boundaries 1/2/9/10, proximity 0/1/2/3/255, same/different previous values, alternate mode, and bus error. Nonzero values such as speed=`0xa7` and asymmetric halfwords were used. Expected JSON was written before actual execution.

All actual dispatch arguments/order, single read callback, original return or reset entry, SP on normal return, and code-byte preservation were checked. Changes to all existing SRAM were either the one declared proximity-byte update or zero. Decoded halfword stack was also confirmed as `ffff0180cdab3412`. Initial address-classification error in semantic lookup was separate from guest execution and corrected with explicit SRAM range checks. The existing 153 executions were not repeated; semantics, dispatch, SRAM results, and original strings were audited from saved evidence.

Private `simulator/touch-event-frame-contract-01` contains `run-contract.py`, `predeclared-expectations.json`, `report.json`, `verify-semantics.py`, `semantic-verification.json`, `annotated-report.json`, and disassembly of three originals. Each bundle SHA/extracted main was checked and original function memory unchanged. Callback data, pretest state, and synthetic stack are explicit inputs. This is a **Unicorn M7 auxiliary experiment** invoking the original handler in-process, not M55 main or physical touch success.

## Next connections

1. Keep default unknown rejection in existing IOM5 peer while adding chunk-read contract for one explicit 16-byte event. Distinguish full 16-byte request from peer delivery in four 4-byte chunks.
2. Check that invalid length, duplicate/exhausted input, different pointer, and disabled option leave existing state unchanged. IRQ/clear/reread semantics need separate evidence.
3. In native execution where original startup/task consumes actual bus data, verify actual dispatch/storage changes and error controls. Then connect GPIO edge/IRQ → task and app/UI consumers.

Later stages of this sequence remain unexecuted, so E11 is not raised to complete. Do not treat unknown GAF as success or change main PC/TCB/returns to manufacture touch success. No physical access, subagents, or external publication.
