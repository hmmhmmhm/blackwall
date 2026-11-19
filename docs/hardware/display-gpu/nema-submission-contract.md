# Original GPU submission and completion-wait boundary

bw-0258. **Original list-submit function executed on Renode M55 and all three firmware images produced identical ring contents, two doorbell writes, and normal function return.** GPU command consumption, completion ID update, IRQ, and pixel output are not yet implemented. Return from submission is not render completion.

## Original execution and synthetic inputs

Existing original ARM 42-word glyph batch and END marker were reused. Original code, branches, and returns were unchanged. Function entry, stack, and ring storage are explicit synthetic tests, not the natural main UI path.

| Point | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| List-submit wrapper | `0x561c0e` | `0x530cfa` |
| List-wait wrapper | `0x561c1c` | `0x530d08` |
| Actual wait-ID path | `0x560f42` | `0x53002e` |
| Low-level ring submit | `0x5634c8` | `0x53fce8` |
| Ring table | `0x2007653c` | `0x20076f04` |
| GPU register store PC | `0x560f68` | `0x530054` |

Addresses were found by checking signatures, post-draw calls, and callees in pinned originals, not by assuming a fixed offset between firmware versions. GPU base `0x40090000` was confirmed by following original ROM pointer load.

Synthetic ring is 64 words/256 bytes. CPU virtual=`0x2100b000`, GPU physical=`0x22000000` were explicitly **different**. Descriptor is at `0x2100b400`, with pool 0, cursor, and queued ID specified. The table's five words were explicitly supplied as descriptor/virtual/physical/capacity/extra length 0. This does not claim restoration of actual main ring table or allocator state.

Original pool information used existing collected low SRAM. Auxiliary M7 rejects reads outside original ROM, collected low SRAM, explicit table/context, and WORK, and rejects all GPU reads. Guest SRAM is read-only. Original flush barriers execute, but physical cache coherency is not verified.

## Actual generated ring

For initial cursor 0, queued ID 7, list address `0x21004000`, and used words 42, original code wrote these 12 words:

```text
000000f0 21004000   # list address
000200f4 0000002a   # original used-word value 42
00000148 00000008   # queued list ID 8
000000f8 00000001   # original IRQ-related request
ff0000f0 22000030   # next address with hold marker
ff0000f4 00000000   # explicitly supplied extra length 0
```

Actual register writes were `0xec←0x22000014`, then `0xec←0x22000034`. Do not confuse virtual ring address with physical doorbell addresses. This record alone does not establish full GPU specification for high command bits and hold behavior.

Original normal list submission passed descriptor used words 42, excluding two END marker words. Passing comparison input 168 to low-level ring function put 168 into packet as well. This evidences that the function does not itself convert byte/word units; it does not verify every actual GPU length mode.

Public API corresponding to original `nema_cl_submit` returns void. Final R0 `0xffffff` is not interpreted as error code. Descriptor ID 8 is **queued ID**, not GPU completion ID.

## Boundary controls

Auxiliary M7 executed per firmware:

- Cursor 0/1/60/61/63: alignment, tail NOP `0x10000`, actual RAM after wrap, and doorbells compared. Not every possible ID-footer wrap position was exhaustively tested.
- Next value after queued ID `0xffffff` became 0; no additional ID/IRQ packet was written. IRQ/wait safety after actual wrap remains unknown.
- Empty list did not change ring. Low-level ring length 0 followed original `-1` return path.
- Nominal code-observer-off control matched final WORK and doorbells. Read guard remained; no memory-write observer used.

Total 30 submit entries. Additionally 21 boundaries ran original list wait up to actual wait-ID callee entry. Only ID 8/0 delivery was observed; **semaphore path and completion return were not executed.** Original wait-ID loop uses separate completion state and semaphore, so no success return is injected there.

## M55 and watch-hook limits

`run_nema_submission_m55.py` replayed three nominal inputs. Original function return, 12 ring words, cursor 12, queued/list ID 8, two doorbells, preserved registers, and SP all matched. Full final WORK SHA matched M7. Command list, surface/canary, and SRAM were preserved.

New `BlackwallNemaDoorbellLatch` records only limited physical-ring values at `0xec`. Other offsets/ranges/flags and reads are rejected before state change. It does not read the ring or generate ID, IRQ, or pixel effects. Shared function watch still treats MMIO writes as unsupported by default; only this fixture can specify exact original store PC, address, width, and value range.

However, **a Renode CPU memory-hook stop must not be treated as pre-access veto.** In the default-watch negative control, first doorbell was recorded by passive sink before write-boundary at the same original store PC was reported. ID remained 7, cursor 4, list ID unspecified; remaining submission did not execute.

Initial negative verifier failed expecting sink writes 0. Raw report/logs were unchanged. A new audit checked actual saved-log results and input/final hashes, establishing scope as **detection after first passive write**. Native was not rerun and failure was not overwritten as successful report. Follow-up comparison conditions check this observation scope. It is not evidence of physical write protection; unsupported peripheral input must be validated inside the method before state changes.

## Evidence and next steps

- `tools/inspect_nema_submission.py`: original function discovery, declared synthetic ring, read boundaries, 30 runs, wait-entry boundaries.
- `tools/run_nema_submission_m55.py`, `tools/renode-nema-doorbell-latch.cs`: M55 submission replay and effect-free register sink.
- Private `nema-submission-contract-02`, `nema-submission-m55-01`, `nema-submission-guard-control-01`: current original inputs/executions and preserved negative failure.
- Private `nema-submission-verification-01/audit.py/report.json/source-pins.json`: **193 checks** of actual logs/RAM/source hashes, both engines, negative observations, and mutation rejection.

Initial contract01 allowed wider SRAM reads. Contract02 specified read ranges and fifth table word and added full packet comparison; M55 used the latter. Python compile passed and work-container exit confirmed. No new physical access.

Next connect list references and payload in this ring to actual GPU-model consumption. Use separate [pixel reference](nema-command-pixel-reference.md), but do not treat unverified sampling, hold/length, and completion/IRQ semantics as implemented. When using actual main ring state, obtain original capture evidence instead of transplanting this synthetic table unchanged.

Remaining full-main SPI, external font-bank, guest framebuffer/viewer, and web installation/recovery conditions remain. **Product 13/29=44.8%, scope v2.** No physical scan/connection/RAM execution/OTA/persistent writes.
