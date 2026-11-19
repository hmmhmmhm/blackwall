# UI font selection and callback initialization state

bw-0251 narrowed evidence of actual font selection after [M55 null-buffer boundary](ambiq-glyph-m55-replay.md). In the simulator, **chains and global head slots created by original main** were confirmed. Callback values matched in snapshots before/after chain creation and fallback links were connected. Final UI draw-unit selection remained unverified. This is not evidence of physical firmware defect or normal screen startup.

## Original code and global slots

| Role | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| Two chain-owner slots | 0x200771d0 / 0x200771d4 | 0x20077a4c / 0x20077a50 |
| Two UI font-head slots | 0x200771d8 / 0x200771dc | 0x20077a54 / 0x20077a58 |
| First chain head | 0x20002954 | 0x20000c64 |
| Second chain head | 0x2000299c | 0x20000cac |
| Chain-head getter | 0x475d66 | 0x470fce |
| Type 0 configuration resolver | 0x475db6 | 0x47101e |

Original initialization creates chains and stores getter returns in UI head slots. Getter's normal path returns owner's first word. Type 0 resolver returns the configuration's object pointer unchanged, not interpreted as a path creating another callback wrapper.

`inspect_ui_font_selection.py` found local instruction patterns reading head slots and passing them to the same style-configuration wrapper. Static candidates: 60 in stock 2.4, 61 each in stock 2.3 and Faceclaw. These are not screen or execution counts and do not evidence all were actually called.

That wrapper passes property ID 90 and font pointer to a lower style function. Pinned [official LVGL v9.3 header](https://github.com/lvgl/lvgl/blob/c033a98afddd65aaafeebea625382a94020fe4a7/src/misc/lv_style.h) also has `LV_STYLE_TEXT_FONT = 90`. This confirms correspondence of constant and call argument, not full vendor-fork/upstream ABI identity. File SHA `9b66f956f3eb456fb1423d6180b2597a8e6baa29c3b16b50b825fa3be6cc53db` and provenance are preserved outside Git in `ui-font-source-research-01`.

## State confirmed in original main

Existing `em9305-reset-main-01` inputs/code/peripheral model reused. **Read-only inspection after original stop** was added to schema2 shared runner. All three images exactly matched existing source CPU state, instruction count, full report state, and events. Stock 2.4 stopped at 0x58253a, stock 2.3/Faceclaw at 0x57b1e2, the existing unsupported SPI DCX configuration. No new main startup boundary was passed.

This source uses invalid-magic diagnostic conditions and existing virtual-peripheral assumptions instead of actual external font-bank. Do not generalize to G2 with normal font-bank. SRAM observation is not a physical device dump.

Each chain linked four previously identified font objects. Global head was first embedded object, followed by second embedded font → external object with descriptor 0 → shared final font. Chain-owner count byte was 4. Other bytes of that word may be heap padding, so full 32-bit value was not interpreted as count.

Compared with initial snapshot, font objects' callback, height, baseline, descriptor, and user-data values matched; only fallback fields changed to form chains. This evidences no callback replacement at those two points, not all callback-write history. External object descriptor 0 remains, so normal external font loading is not inferred.

Actual observed objects/configuration/owner records were copied into read-only SRAM and original type 0 resolver executed 24 times, original getter six times, original style-delivery prefix six times, 36 total. Getter returned observed head; style prefix passed same pointer and property 90. Allocator, logging, and full style storage were not replaced with success stubs. Style test stops on lower-function entry, so it does not evidence style being stored on actual UI object.

## Null-buffer interpretation and next boundary

The explanation that “a completed chain may replace head with another wrapper” is **not supported in this diagnostic snapshot**, since actual head is the existing embedded object. Earlier null-buffer test remains valid as execution of that embedded callback on the Ambiq path.

However, actual display work selecting that Ambiq callback was not yet confirmed. Possibility of software draw unit or another evaluation/distribution path must be investigated. Do not patch null branch or bypass protection checks. Next trace draw-unit registration, eligibility, and job dispatch to connect actual UI path and function fixture.

## Evidence and failure records

Canonical material outside Git:

- `ui-font-selection-contract-04`: slots, instruction patterns, pinned originals, schema2 diagnostic plan.
- `ui-font-state-main-02/stock24`, `/stock23`: original main post-stop states.
- `ui-font-state-main-cfw-90-01/cfw`: Faceclaw post-stop state.
- `ui-font-state-native-audit-01/*`: common semantic-contract reaudit of three saved runs, no native rerun.
- `ui-font-selection-verified-02`: 36 original-function tests and snapshot comparisons.
- `ui-font-selection-verification-02/audit.py`, `report.json`: **834 checks** of original bytes, candidates, callbacks, fallback, heads, logs, pinned provenance.

First static check used wrong push-register mask; next assumed version-specific push differences had identical bytes and failed. Checks were changed to original decoder roles/instruction structure. First main observation limited valid owner-record addresses to low SRAM and missed heap objects in system SRAM. Existing board-mapped ranges were checked and only observation range changed before rerunning stock 2.4.

First 45-second Faceclaw observation ended its host window before original strict boundary. Execution handle exit/container removal were confirmed; result not adopted. A separate plan extending only host observation window to 90 seconds confirmed exact match with existing boundary/state. Raw failure and incomplete results preserved; firmware, peripherals, branches, and PC unchanged.

First saved audit failed because frozen tool copy lacked `native_replay` import dependency. `verified-02` and separate `verification-02` included dependency copy; native was not rerun. Python compile passed.

Overall product fulfillment 13/29=44.8%, scope v2. Full-main app loop, GPU execution, integrated screen, and remaining web installation/recovery conditions remain. No glasses, case, or actual persistent-storage access.
