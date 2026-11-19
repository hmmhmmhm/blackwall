# Full CQFLAGS Read and Retention Contract

Task bw-0184. Analyzed the next `400612B0` read in three originals without changing the model. This is MSPI1 CQFLAGS. Source was tied to peripheral name, type, and address to avoid confusion with the identically named IOM register. MSPI offset is `2B0`, mask `FFFF`, and CQPAUSED bit 3; IOM has offset `234`, an upper IRQ mask, and a different flag layout.

## Use in actual original code

The stock 2.4 original function at entry `4E8F8C` (stock 2.3/CFW `4DBBB8`) is a retention save/restore path. Its actual caller passes R1=2 and R2=1. The current read instruction reads the entire CQFLAGS word and saves it at MSPI state+`8B8`. The opposite restore path uses LDRB at the same location, applies an FF mask, and writes CQSETCLEAR. It does not restore saved upper hardware flags unchanged.

This agrees with `regCQFLAGS` save and `regCQFLAGS & 0xFF` restore in pinned HAL `am_hal_mspi.c`. Compared actual instructions, save addresses, call arguments, and pinned source across three original images. At this stage the read had not been executed to observe its return value, RAM store, or restoration.

## What can be calculated and what remains unknown

| CQFLAGS bits | Meaning | Basis in current virtual state |
| --- | --- | --- |
| 7:0 | Software flags | Stored value `80` |
| 10 | CMDCPL | PIO CTRL.STATUS=1 |
| 11 | DMACPL | 0 in the disabled model, which has never allowed DMA |
| 14 | CQIDX | Match condition for stored CURIDX=ENDIDX=0 |
| 15 | STOP | 0 in the model, which does not allow CQ execution/stop |
| 8/9, 12/13 | Selected peer buffer XNOR/XOR | External handshake inputs unknown |

In the current model state, known value calculated from source meanings is `4480` with known mask `CCFF`. External handshake mask `3300` is unknown. This is not a physical flag measurement; index comparison in particular is a digital interpretation of the source's match description. Do not use resetValue 0 as evidence that all current dynamic flags are 0.

MSPICFG.IOMSEL=7 is IOM7. The source's DISABLED selection is 15 and explicitly fixes input to 0 only in that case. Thus current selection 7 cannot be treated as disconnected. The connection and timing relationship between existing IOM7 software flags and actual MSPI handshake wires are also unverified.

## Scope of next implementation

With default unknown, retain the existing block on full reads. Only when an explicit two-bit mock buffer input 0..3 is selected should the model synthesize software bits, PIO completion, index conditions, and paired XOR/XNOR flags. Input 0 yields example `4780`, input 3 yields `7480`. These illustrate selected virtual states, not actual IOM7 inputs or actual CQ execution.

Supply PIO completion through a separate interface that does not increase guest CTRL read count. Do not add CQ/DMA enable, fetch, IRQ, or STOP behavior at this stage. Compare how original RAM snapshots and low-eight-bit restoration respond to mock upper bits. Do not return a software-only value as full flags or unconditionally fill unknown upper bits with 0.

`simulator/mspi1-cqflags-contract-01/report.json` outside Git, produced by `tools/inspect_mspi1_cqflags_contract.py`, uses 42 checks to verify source pins, exact peripheral/bit layout, save/restore in three originals, and current disabled state. The IOM definition found in an initial global text search was not used as MSPI evidence; structured peripheral selection checks distinguished the layouts.

Overall progress was 13/29 (44.8%). CQ execution, DMA, external inputs, full boot, display, and physical recovery remained incomplete. No glasses access, installation, RAM execution, or persistent write occurred.

An inherited-parent-model read-only review reported no additional material address or storage-interpretation errors. Because the IOM1READY XNOR counterpart description is ambiguous, corresponding buffer pairing is limited to a mock assumption. Later actual storage results are recorded in the [CQFLAGS mock model](mspi1-cqflags-mock-model.md). Unimplemented/unobserved statements above describe the scope at bw184. No Astra, other model-family review, or full transcript-file audit was performed.
