# Natural touch wake contract across original families

bw-0452. Recent natural main integration of app 1 wake was limited to stock 2.4. This work extends the same IOM5/GPIO27/actual UART peer-reply inputs to stock 2.3 and Faceclaw. Existing 16 conditions, unresolved gesture/ring support scope, and incomplete normal GAF and screen remain.

## Source-confirmed differences

Pinned raw hashes of three originals and existing verified sync transport/UI metadata are reused. Four original instructions before the gate, `[r0,r1,r2,r3]=[1,0,0,0]`, BL target, unique BL of finish API caller, and app 1 callback in actual registry are checked.

| Point | Stock 2.4 | Stock 2.3 | Faceclaw38 |
| --- | --- | --- | --- |
| Scheduler wake caller return | 467a7e | 467d6c | 467d6c |
| Original app request producer | 46a5ae | 46a672 | 46a672 |
| Actual wake BL target | 46a5ae | 46a672 | 7d3c00 |
| UART finish caller return | 469d1c | 469de8 | 469de8 |
| Registry app 1 callback | 4b7a58 | 4ad7e4 | 4ad7e4 |

Faceclaw replaces two scheduler calls with hooks. On double-click it enters `7d3c00→7d3c14` and checks additional state; on the unmet-condition path, `7d3c7e` constructs Thumb pointer `0x46a673` and returns to the stock producer. Other path results are not automatically assumed to be app 1. Hook entry, selection conditions, stock fallback, and separate branch point are observed.

## Experiment scope

Use 16-byte double-click frame `020800003412cdab0180ffff5ac317e9`, 1 ms falling/high pulse, existing source peer ACK, and one display reply. Reuse the previously verified opt-in UART RX timeout model. Each variant uses source-checked gate/sender/UI addresses; raw hashes and actual instructions per family replace stock24-only scope checks.

These two families retain default 10 MIPS and stop at **UI callback entry**. Speed input is not transferred without newly verifying that family's HP time profile. Callback return, full app initialization, and drawing are not completion judgments for this entry capture. Existing stock24 return evidence remains separate.

Observation does not change source or device model, but scheduling differences due to hooks are possible. Original opcodes, PC, TCB, ready state, and returns are not forced. Record whether the custom hook selects stock fallback in actual state; do not overwrite unexpected results as success.

## Actual execution of two families

Two fresh M55 runs of stock 2.3/Faceclaw38 delivered the same double-click after original reset via GPIO27 falling → IRQ56 → registered callback → original input task → IOM5 16 bytes/four chunks. Original slider arguments were role 1, code 1, 0, 0.

Both returned through scheduler wake caller, and original UART task sent packet `0201010000000000` on channel 2, ID 800d. ID was read from actual packet/descriptor and one 12-byte reply 2/channel 0 matching source contract placed in FIFO. Replies were not duplicated to meet RX threshold.

Actual IRQ31 showed raw 0x61, masked 0x40, pending 12, timeout latch 1. Original code read 36 bytes total (initial ACK 24 + display reply 12), and pending/timeout returned to 0. UI producer → app 1/type 2 dispatch → registered callback `0x4ad7e4` followed. Actual current TCB was original `ui_task`; Thread mode, original stack, arguments, and context[0x1c] at callback entry were checked.

The two old-family `strict.cs` files are byte-identical. Boards differ in one existing case-specific `vendorStartupHex` field, each exactly matching the pinned prior bw445 board. Apart from that field boards are byte-identical. Mains use pinned stock 2.3/Faceclaw inputs. This difference is not hidden as fully identical input. CPU registers were identical before/after UART FIFO input; execution stopped at callback entry. Callback return or subsequent initialization completion across all three images is not claimed. CFSR/HFSR, memory-protection violations, strict guards, and trace overflow were 0; all owned containers were cleaned up.

## Actual Faceclaw hook selection

CFW trace recorded `7d3c00→7d3c14→7d3c74→7d3c7e→46a672`. Separate custom branch `7d3c8e` was not observed. Custom-state pointer slot `0x2029f59c` was 0 before input and in final snapshot. In this state no valid custom state exists, consistent with original execution selecting stock fallback. The host did not create custom state or enable the feature.

Faceclaw wrapper calls the stock producer while retaining a 16-byte outer frame from push/sub. Actual producer SP was 16 bytes below scheduler gate, and gate SP returned to its original value after wrapper exit. Stock 2.3 producer SP matched gate SP. Identical result packets do not imply identical original paths.

This is Faceclaw fallback integration evidence under current conditions. A valid custom state with the hook choosing custom UI remains unverified.

## Current input support scope

| Original | Natural double-click → app 1 callback entry | Callback return | Screen |
| --- | --- | --- | --- |
| Stock 2.4 | Existing bw446 evidence | Confirmed in bw448 HP interval | Incomplete |
| Stock 2.3 | Confirmed in this native run | Unverified | Incomplete |
| Faceclaw38 | Confirmed in this native run and actual hook fallback | Unverified | Incomplete |

Wake entry is connected across three originals, but gesture/ring support list, additional input lifetime, full integration of invalid/duplicate inputs, and E11 as a whole remain incomplete. Normal GAF, drawing, and pixel completion criteria remain. Existing no-input and invalid frame/ACK controls are not extended to all wake error handling in new families.

Final saved audit's 48 checks confirmed per-original actual call/return addresses, device input, original UART packet/timeout IRQ, UI task/context, actual Faceclaw fallback/stack release, existing case-specific fixtures, and process cleanup.

The first saved audit failed by assuming boards were completely identical. The failed check was preserved, and the actual one-field difference and existing case-specific fixture pins were independently compared. Firmware/execution were not rerun and differences were not ignored to pass.

Private `simulator/touch-wake-families-research-01` source contracts, pinned builder/observer, verification, and two native captures are preserved by `simulator/touch-wake-families-manifest.json`. Original 2.4 was not redundantly rerun. No physical device, subagents, or external publication.
