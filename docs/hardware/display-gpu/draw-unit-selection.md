# Original draw-unit registration and label selection

bw-0252 investigated registered draw units and job selection after [UI font selection](ui-font-callback-selection.md). In all three original mains stopped under diagnostic conditions, **one unit with Ambiq callbacks** was confirmed. Original label evaluation and job-selection functions were also executed. Actual screen frames or GPU execution were not confirmed.

## Registered objects

| Item | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| LVGL global base | 0x20070748 | 0x20071388 |
| Ambiq unit global slot | 0x200771c0 | 0x20077a38 |
| Evaluate callback | 0x4eb7b0 | 0x4e10f0 |
| Available-task entry | 0x499d22 | 0x48de3a |

Original registration code creates a unit and stores callback pointers. There was one direct BL candidate to the creation function in each image. This static search alone did not exclude other indirect registration.

Existing original main execution was reproduced, then after stopping list head at global `+0x13c`, count at `+0x140`, and actual 228-byte unit were read. All three had count 1, head and Ambiq global slot pointing to the same object, next=null. Registered dispatch/evaluate pointers matched original Ambiq registration code. No separate software unit was found in the list at this point. This does not mean there is no software path at every time or in physical hardware configuration.

Object debug idx is 1, not the same field as preferred unit ID 9 below. Pinned [official LVGL private header](https://github.com/lvgl/lvgl/blob/c033a98afddd65aaafeebea625382a94020fe4a7/src/draw/lv_draw_private.h) describes name/idx as debugging. Actual vendor offsets and control flow were independently compared against original instructions. Entire upstream/vendor ABI is not assumed identical.

## Original function execution

Actual captured unit object and count were placed in read-only virtual SRAM; original ARM functions ran with synthetic task/layer arguments. Opcodes, branches, and returns were not replaced; no observer hook. This is a function-entry fixture, not a job naturally reached from reset.

- Label type 5 evaluation: combinations of initial preferred ID 0/1/9, score 0/10/255, descriptor pointer 0/valid work area/unmapped. 27 cases per image, 81 total. All recorded ID 9/score 10 and returned 0. This path read neither descriptor nor font, so it cannot be assumed to filter callback null-buffer issues through font-based eligibility. Return 0 is not immediately interpreted as job rejection.
- Type 0/4/12 controls retained existing ID/score: nine cases total.
- Original available-task function with registration count 1: 12 combinations of state 0/1/2/3 and requested ID 0/9/99 per image. Only head state 1 returned that task; requested ID did not affect result. 36 cases total. Pinned upstream enum 1 is QUEUED, but direct evidence here is original `state==1` comparison.
- Empty layer head returned null in all three images.

Total **129 original-function runs**. SP and callee-saved register restoration, protected SRAM, and final work-memory change ranges were checked. This is not a result of competition among two or more units or processing an actual screen task.

Current diagnostic registry/selection conditions support that Ambiq label path is eligible. There is therefore no basis to conclude “actual UI uses software and avoids the earlier read.” Conversely, no claim is made that an actual frame executed that point.

## Newly identified limit in interpreting null read

Board memory map was rechecked during this investigation. Integrated main board maps **ITCM from address 0 to 0x40000**. Earlier standalone M55 function fixture lacked this area. Identical address 0x10 access failures in both engines could therefore be affected by the same fixture omission, not evidence of actual G2 HardFault or firmware bug.

At 0x10, existing main ITCM prefix has host A5 fill; actual hardware value was not obtained. This value was not treated as normal data to pass the full call. Next check through original data flow whether the loaded value is used on raw-bitmap return path and compare function tests reflecting the same map as integrated main. Do not solve by skipping original branches or unconditionally returning 0. Existing strict-failure evidence is preserved.

## Execution and evidence

New `inspect_draw_unit_selection.py` locates registration, callbacks, fast path, and schema2 diagnostic plan in three pinned bundles. `verify_draw_unit_selection.py` compares main state and original-function tests.

Canonical material outside Git: `draw-unit-selection-contract-01`, `draw-unit-state-main-01/{stock24,stock23,cfw}`, `draw-unit-selection-verified-01`. Existing main stop PC, instruction count, full report state, and events exactly matched source. Model, board, and original PC were unchanged; only post-pause reads and 90-second host observation window were added. This run retains existing missing-font invalid-magic and virtual peripheral diagnostic assumptions, so it is not normal font-bank/physical boot verification.

`draw-unit-state-native-audit-01/*` reaudited common semantic contracts of three saved runs without native rerun. **585 checks** in `draw-unit-selection-verification-01/audit.py` confirmed actual logs, input/source hashes, original instruction bytes, registry callbacks, range of 129 function results, and pinned upstream reference files. Python compile passed. Removal of all work containers was confirmed.

Overall product fulfillment remains 13/29=44.8%, scope v2. Remaining web installation, independent recovery, integrated main app loop, GPU execution, framebuffer, and screen conditions remain. No actual glasses, case, or persistent-storage access.
