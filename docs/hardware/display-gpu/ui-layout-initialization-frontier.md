# Progress boundary in original UI layout initialization

bw-0448. bw447 confirmed actual font lookup returned, but app initialization completion and natural drawing were incomplete. Here the saved tree and original traversal/update termination conditions were checked and layout calls observed under the same execution limits. All 16 conditions and default 10 MIPS board remain.

## Tree and current recursive path

Stock 2.4 `0x45119a` reads a 16-bit child count at +0x30 of the accessory pointer at object+8. Original recursive function `0x441390` traverses the child array at that accessory structure's first word. Saved root `0x20299698` was interpreted after comparing actual load and BL.

- Tree has 54 nodes and maximum depth 10. No repeated visits of the same node or inconsistent parent/child backreferences.
- Parent, child count, selected index, and LR were checked in eight 16-byte recursive frames on original stack. Selected child matches next frame's parent.
- Actual prologue and 72-byte frame of innermost `0x43f7c4` also bind preserved current object `0x2029b70c`.
- At that time 23 nodes had bit 0 set; root alone had bit 2. This is one snapshot, not a guarantee of termination for all future updates.

`0x43fc8c` checks a marking byte during update, clears root bit 2, and performs depth-first traversal. If bit 2 is set again after traversal it repeats; otherwise it returns to original caller. Recursive function clears each object's bit 0 then calls geometry update, with additional processing according to bit 1. Simple child cycles are distinct from additional updates caused by dirty-state reset.

## New observation at default 10 MIPS

Reran from original reset under the same 1000 ms virtual limit and 30-second host limit. Original model/board, font, and object data were unchanged. Observer stores per-function call counts, first/last contexts, visit counts for at most 256 objects, and at most 64 root-update samples. Hook scheduling noninterference is not claimed.

- Observed 480 recursive entries and 38 objects.
- Observed 19 root-update pass entries and 14 actual epilogue arrivals at `0x43fc8c`. Passes and function invocations are not the same unit, so 14/19 is not a completion rate.
- Subsequently entered original kind 4 creation function `0x5417a4` at index 3. Interpretation that it is permanently stuck in the first fixed layout pass is inconsistent with this run.
- App initialization return, UI callback return, and Ambiq glyph draw entry were all 0. CPU faults, strict accesses, memory-protection violations, and observation overflow were 0.

Final observation time was about 1022 ms after UI dispatch, including excess due to host polling. Counts/time are not interpreted as physical performance or full UI completion.

## Explicit HP-interval control

At default 10 MIPS, [independent HAL delay test](../cpu-memory/hal-loop-time-profile.md) calculated actual code's 5 µs request as about 80.9 µs. Previously verified `hal-loop-equivalent-v1` HP 167 MIPS is applied only to the interval after UI dispatch pause in a separate candidate. This is not an actual per-instruction cycle model.

Transition requires whole-machine pause, original 10 MIPS prefix, and actual HAL mode field 2. Only host input changed is PerformanceInMips. Registers, cumulative instructions, SRAM, virtual time, STIMER, and WDT CFG are checked unchanged before/after transition. Original timeout, watchdog, PC, branches, and readiness remain unchanged. This control is not automatically adopted as default board or dynamic clock-switch implementation.

## Actual return in HP candidate

Actual mode word 22 (field 2), pause state, 10→167 MIPS applied. All general registers, instruction count, virtual time, STIMER, WDT CFG, and full SRAM were identical before/after. Raw, model, board, and five SRAM snapshots from reset → UI dispatch were byte-identical to default candidate.

HP candidate observed 3,019 recursive entries, 74 objects, 58 root passes, and 30 update-function epilogues. Original kind 4 creation returned to caller `0x53270e`; app initialization and UI callback reached original continuations `0x4b7ad4` and `0x4456ec` respectively. Original `ui_task` and Thread mode remained; 32-byte SP release from callback entry to caller also matched original dispatch frame.

Nominal virtual 123.3993 ms from UI dispatch to callback caller is an observation under this uniform instruction-rate profile, not evidence of physical time, actual speed, or per-instruction cycle accuracy. Default 10 MIPS candidate failure is not established as firmware infinite loop or hardware error.

Ambiq letter entry remained 0 through this checkpoint. App initialization completion and screen completion are separate. At the next normal pause, perform a bounded 100 ms follow-up to observe source-identified draw/target/submit/ring/display frame boundaries, without relaxing guards or branches.

## Natural-render boundary after callback

A separate fresh candidate resumed normally from whole-machine pause after original callback return. It recorded first/last samples and counts at source-identified draw, target, submit, ring submit, display producer, and frame wrapper, targeting first actual submit entry as stop. No new virtual device response was added.

All six boundaries were 0 in the next virtual 100.057 ms. Final PC `0x4f555a`, actual current task still original `ui_task`. Linked RTOS state lists, current task, and saved contexts of other tasks were checked. Alongside cumulative 64 root passes, 34 update epilogues, and 3,731 recursive entries, this confirms UI work continued after callback. These counts include pre-callback totals.

Protection violations, CPU faults, and observation overflow were 0. Collection occurred at normal pause; no aborted VM was resumed. Since draw callback was not reached, framebuffer, pixels, and frame completion remain unverified. Next narrow UI processing after callback and refresh/draw dispatch conditions using source and saved execution. Do not yet conclude a particular device blocks it.

## Reverification and scope

Private `simulator/ui-layout-research-01` preserves original tree, eight recursive frame path, pinned runner/observer, time profile, saved audits, and linked task graph. Three fresh native runs—baseline, HP, callback follow-up—and source/docs snapshots are hashed in `simulator/ui-layout-manifest.json`.

Final 23 saved-audit checks cover source structure, legitimate calls/returns, initial-interval and device-byte identity, state preservation across explicit timing input, actual UI task and unreached subsequent boundary, guards, and process cleanup. They do not prove observation neutrality, chipset cycle accuracy, physical timing, normal GAF, or completion of all required services.

Overall acceptance remains 10/16=62.5%. E09/E11 are partial. No physical access, persistent writes, subagents, or external publication.
