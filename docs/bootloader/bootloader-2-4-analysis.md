# Bootloader 2.4 support investigation

Recorded 2026-11-10. Goal: identify the actual changes needed for 2.4 support, independently of the version chosen for support. This document is not yet a supported profile or an applicable patch.

Boot 2.3.2.14 and 2.4.0.24 extracted from official bundles were compared. Their full lengths are 149,760/149,773 bytes respectively, and the reset vector changes from `0x00432CA3` to `0x00432CB3`. Although most later code differs at the same offsets, a simple byte count is not evidence of the amount of functional change.

## Confirmed candidates

| Item | 2.3.2.14 | 2.4 candidate | Observation |
| --- | --- | --- | --- |
| manager hook | 0x0042E656 | 0x0042E666 | Existing BL bytes match; target flag function moved |
| update handoff hook | 0x0042E3D4 | 0x0042E3E4 | BL target moved to new handoff |
| boot handoff hook | 0x0042E440 | 0x0042E450 | Same |
| flag function | 0x0042E56C | 0x0042E57C | Similar entry; internal call displacement needs review |
| vector handoff | 0x0042DFD8 | 0x0042DFE8 | Selected instruction span identical |
| MRAM wrapper | 0x0042E83C | 0x0042E84C | Entry span identical; internal callee also moved |
| UART pin table | 0x00434210 | 0x00434220 | Selected data span identical |
| UART wake/sleep | Same address | Same address | Entry prefixes match, but PC-relative literals and callees changed |

Code addresses here exclude the Thumb bit. Rebasing every address by +16 is incorrect. Matching entry prefixes alone do not establish ABI or RAM-state preservation. Disassembled strings without specified code/data boundaries and lengths are not used as evidence.

Still to verify: UART driver RAM slot initialization, placement and lifetime; callback preservation; manager/DFU stacks and priorities; meaning of changed callees and literals; full MRAM wrapper chain and ROM binding; boot ITCM/watchdog state; alignment of added code; and normal/pending-update/handoff control flow. The current append link address `0x00434900` is before the end of the new original and cannot be reused as is.

## Reproduction material

[Candidate comparison JSON](../data/bootloader-binding-candidates.json) contains only address and selected-span comparisons. Raw byte evidence and the read-only analysis script are outside Git at `~/Library/Application Support/Blackwall/recovery/boot-2-4-analysis/`. The script checks exact original SHAs of both bundles and only compares candidates; it generates no patch, bootloader, or OTA file.

Current conclusion: candidates for support have been narrowed, but 2.4 support is incomplete. Nothing was installed on hardware and support checks were not bypassed.

## Follow-up direct comparison of instructions and literals

Following the user's direction, analysis was extended directly without contacting the creator. `tools/compare_boot_bindings.py` checks pinned SHAs and all component CRCs and boundaries of both official bundles, then compares specified Thumb instruction spans. It was run with Capstone 5.0.9. Raw disassembly is retained outside Git as `boot-2-4-analysis/instruction-comparison-02.json`. The specified spans define the analysis scope; they do not prove all function boundaries.

Changes found:

- In the 116-byte UART wake span, the RAM base literal is `0x20000458` in both versions. The literal pool moves `0x41F9C8`→`0x41F9D8`, and the direct call moves `0x422EF0`→`0x422F00`. Other than these two changes, instruction/operand comparison found no differences in the span. Equivalence inside the callee requires separate verification.
- The 94-byte UART sleep span reads the same RAM base. Two in-code literals move `0x4345D8/0x4345DC`→`0x4345E8/0x4345EC`, and the call target moves as above. The meaning of data addressed by these literals is not yet established.
- **The `0x41F918` path is not a simple relocation.** It is a large function's prologue in the older version, but in 2.4 it is a short wrapper setting `r3=0` and calling `0x41F924`. The new inner function preserves incoming r3 and stores it in stack descriptor `+0x0C`; the old function stores 0 in that field. Default calls to the same external entry suggest similar intent, but do not prove full equivalence.
- Upstream recovery patch UART transmission directly writes the UART2_DATA register in `bootloader.c`; platform.h has no direct binding to `0x41F918`. Thus this change is not by itself evidence of a direct recovery-transmission ABI break. Indirect calls and initialization paths remain to trace.
- Decoding confirmed that the three hook candidates BL-branch to the new update-flag and vector-handoff locations. The 18-byte vector-handoff comparison span is identical. This is not extended to surrounding control flow.
- The 2.4 original ends at `0x43490D`, so the existing append address `0x434900` overlaps its final 13 bytes. The first 16-byte-aligned location after the original is `0x434910`. This is only a placement candidate and must not be used without linker, full-size, and RAM verification.

The tool decoded all nine specified spans to the requested lengths. Comparing the same instruction index in UART transfer spans of different lengths serves only to locate changes; it does not establish semantic correspondence or a change percentage. No patch or installation file was generated.

Next direct analysis targets wake/sleep callee `0x422EF0`→`0x422F00`, MRAM wrapper callee `0x42E7E8`→`0x42E7F8`, UART state initialization, and callback slots. The same RAM address alone does not imply the same lifetime or ownership. After obtaining that evidence, assess whether a local build and simulated verification of a 2.4-specific recovery patch are possible.

## MRAM call path and execution comparison

The traced call path follows. Addresses exclude the Thumb bit.

| Stage | 2.3.2.14 | 2.4.0.24 |
| --- | --- | --- |
| 16-byte alignment-check wrapper | 0x42E83C | 0x42E84C |
| Convert address to word offset, call, and handle status | 0x42E7E8 | 0x42E7F8 |
| Indirect ROM call and MMIO postprocessing | 0x42EBF4 | 0x42EC04 |
| Function-pointer table | 0x433540 | 0x433550 |
| ROM entry at table +4 (including Thumb bit) | 0x0200FF21 | 0x0200FF21 |

The first four words of both tables also match. ROM code itself was not part of the bundle under examination; the same address alone does not establish identical ROM across different silicon. The comparison was extended to 84 bytes of the inner function and 30 bytes through ROM dispatch return. MMIO addresses after dispatch are both `0x40014008` and `0x40014024`. Only the first 128 bytes of the UART callee were additionally observed; full-path analysis remains.

`tools/emulate_mram_binding.py` executed hash-pinned original code from both versions with Unicorn. Four destinations × four word counts × three simulated ROM statuses = **48 pairs, 96 runs** compared and checked:

- Violating destination 16-byte alignment or word-count multiple-of-four conditions returns `0x08000140`, with no ROM call or MMIO write.
- Valid inputs pass key, operation=1, source, `(destination-0x400000)/4`, and word count to the same ROM entry.
- Simulated ROM status=0 returns 0; other selected statuses return `status | 0x08000100`.
- Three MMIO writes from dispatch, restoration of simulated previous PRIMASK=1, and restoration of the pre-call stack position match.

ROM entry and three critical-section helpers are stubs; actual writes, permissions, cache, power, and silicon behavior were not verified. This lower wrapper also passes count=0 to ROM; do not confuse that with upstream `recover.c`'s length=0 early return. This compares execution of the specified adapter path, not full upstream recovery.

**Negative control:** Calling old wrapper address `0x42E83C` in the new 2.4 original fails with an unmapped fetch in this model. That location is not the new wrapper entry but an instruction inside the inner function. A 2.4 port cannot reuse upstream `src/examples/recover.c`'s hardcoded `0x0042E83D` unchanged. Bootloader and RAM recovery payload must use the same verified version profile.

Results are retained outside Git as `mram-emulation-02.json` and disassembly as `instruction-comparison-03.json`. Emulator success is not presented as physical recovery or full 2.4 boot support. Next compare the full UART callee, state initialization, callback ownership, and critical-section helpers.

## UART state slots and wrapper execution comparison

`tools/emulate_uart_binding.py` executed wake/sleep wrappers from both originals: two operations × two modules (UART2 and out-of-range 4) × three initial awake values (0/1/255) × two simulated power returns (0/7), totaling **24 pairs, 48 runs**. GPIO and power callees are stubs; actual UART, pin, and power behavior was not tested. Results are retained outside Git as `uart-emulation-01.json`.

- UART2 handle is `0x20000494`, pin table pointer `0x20000498`, and awake byte `0x200004A8`. For every valid input compared, all of the 112-byte driver state except the awake byte was preserved. A nonzero sentinel was placed in the receive callback and checked for preservation.
- Wake passes the handle and `(mode=0, arg=1)` to the power callee, calls GPIO `(44,4)`, `(42,4)`, then writes awake=1. **Even with callee error=7, awake=1 and the return value is 7.** Software awake is not proof of successful activation.
- Sleep first writes awake=0, calls GPIO `(44,3)`, `(42,57475)`, then calls the power callee with `(mode=2, arg=1)`. 57475 is the decoded configuration word and must not be replaced with simple mux number 3. Traces matched between versions.
- Module=4 returned 1 with no calls or driver writes. Not every uint32 module input was verified.
- Upstream `bootloader.c` checks both WAKE return 0 and the actual power status bit before later SLEEP. These tests do not justify weakening that check.

Additional static comparison examined 208 bytes of RX dispatch at `0x41F776`. Driver entry size is 0x1C; a nonzero callback at `base + module*0x1C + 0x14` is called indirectly. UART2's resulting address is **0x200004A4**, matching the upstream binding. Changes in this span are two literal-pool locations and two calls to receive callee `0x423610`→`0x423620`. When the callback is set and safely cleared remains unproven.

All 356 bytes of initialization candidate `0x41F612` were also decoded. The entry remains the same, but five callees and pool/table locations change. This is retained in `instruction-comparison-04.json`. It traces candidates, not full initialization/ownership verification. Next trace this candidate's state registration points and callees, and two power callback slots checked by recovery.

## Power callback table initialization and dispatch

The two power callback addresses themselves were not found as 32-bit boot literals. Examination of nearby RAM addresses found a **0x20026E38** table base pointer at `0x41D11C` in both versions. After finding candidate literal references in adjacent code, the following function entries and call paths were separately decoded and executed. Output interpreting data as instructions during candidate search was not used as function evidence.

- The 22-byte wrapper at `0x41CD34` calls table +0x0C, or **0x20026E44**.
- The 22-byte wrapper at `0x41CD4A` calls +0x10, or **0x20026E48**.
- Both wrappers return 0 for null, or call the non-null callback and pass through its return value. The pre/post names are the upstream platform.h interpretation; they do not prove the entire actual power sequence here.
- The first 20 bytes of initializer `0x41CE52` call `0x41560C` with table address, length 0x3C, and value 0. Execution continued until RAM was actually cleared, stopping at `0x41CE66` before the first MMIO access. Sentinels before and after the table remained and only 60 bytes became 0.

`tools/emulate_power_callbacks.py` passed **9 pairs, 18 runs**: one initialization pair and eight pairs for null/non-null and callback returns 0/7 across two slots. Null combinations include redundant conditions because the configured return is unused. Callback bodies are stubs, but memory clearing executed original code. Final state of all RAM except the stack work area was also compared. Results are outside Git as `power-callback-emulation-01.json`.

While writing the test tool, a Unicorn memory-write hook was observed reporting candidate addresses for canceled conditional STM writes. This was not reported as an out-of-bounds firmware write. Code trace and actual RAM after execution confirmed preservation outside the table, and the check was changed to final RAM comparison. This does not prove the full instantaneous write history.

Remaining work includes the boot path executing this initialization before the manager hook, subsequent table registration/reset paths, UART state registration, and interrupt contention. These tests alone do not establish safe runtime ownership.

## Tracing initialization callers and manager entry order

Thumb BL-format candidates were searched at every halfword position in the pinned-SHA raw images, and relevant callers compared with surrounding code. This search is not a call graph that fully separates coincidental instruction patterns in data or indirect calls. Result fields are labeled `direct_bl_candidates_not_reachability_proof`.

| Call | 2.3.2.14 call site | 2.4.0.24 call site |
| --- | --- | --- |
| power table initializer 0x41CE52 | 0x41C57E | 0x41C57E |
| pre callback wrapper 0x41CD34 | 0x41BFC2, 0x41C20E | Same |
| post callback wrapper 0x41CD4A | 0x41C064, 0x41C2CE | Same |
| UART initialization candidate 0x41F612 | 0x430538 | 0x430548 |

The UART caller is inside a 30-byte wrapper at old `0x430526` / new `0x430536`. Both versions call five functions in the same order, with UART initialization fourth. Surrounding function addresses each move +0x10. A Thumb pointer to this wrapper was found at old `0x433880` / new `0x433890`. The pointer's consumer and full reset→init order remain to trace.

Manager entry is old `0x42E640` / new `0x42E650`; the 26-byte span through the hook was compared. The sequence of entering the update-flag function after four helper calls is the same. Call order at this point corresponds, but the global execution order of board init and manager is not proven. Details are in `instruction-comparison-06.json`.

The assumption that the existing pin table address appears directly as a literal pointer in the original was not confirmed. The UART table pointer may be set by calculation, restoration of initial data, or another path. Failure of a simple pointer search is not interpreted as table absence or an ABI break; trace actual registration.

## Confirming initialization table execution order

The table consumer was found at old `0x41F9F8` / new `0x41FA08`. It copies the original table to RAM `0x20022E00`, sorts eight-byte entries by their second word, and calls non-null function pointers in order. The original table contains four entries.

| Analysis name | Old entry (including Thumb bit) | New entry | Sort value |
| --- | --- | --- | --- |
| Board init including UART initialization | 0x430527 | 0x430537 | 1 |
| Second value-1 initialization | 0x431C9D | 0x431CAD | 1 |
| Value-25 initialization | 0x415591 | 0x415591 | 25 |
| Value-26 initialization | 0x41FD71 | 0x41FD81 | 26 |

`tools/emulate_init_dispatch.py` executes copying, sorting, and dispatch using original instructions, stubbing only initializer bodies. Both pinned images called each once in the order shown. The order of the two value-1 items was observed for these two actual inputs, not a general stable-sort guarantee. Preservation of RAM-copy entries, surrounding sentinels, and stack restoration were checked.

Runs used simulated returns of 0 for all initializers and 7 for all initializers. **Even with return 7, execution continued to the next item.** Completion of all calls is not interpreted as successful initialization. Original recovery patch entry-state checks must be retained. Results are outside Git as `init-dispatch-02.json`; this is not a full-boot success test.

Old caller `0x41B862` calls this dispatcher with a BL at `0x41B86A` and proceeds to UART1 wake and several initialization paths. Manager entry `0x42E641` is passed in separate code to thread creation function `0x4160FE` (literal load `0x42E6F0`, call `0x42E6F2`). The higher-level scheduler start and manager-thread creation path still requires tracing, so the entire reset-to-manager order is not claimed as established.

## Actual execution of boot data initialization

To investigate sources of pointers not found by literal search, original data initialization dispatchers at old `0x432D24` / new `0x432D34` were executed. This code traverses PC-relative descriptors and calls each handler indirectly. `tools/emulate_boot_data_init.py` runs the original without stubbing handlers and does not map peripheral MMIO. The boot image region is read/execute-only. SRAM/ITCM were filled with 0xA5 so initial zero values could not make checks pass.

Both versions returned normally and restored the stack; the following values were actually initialized. Results are outside Git as `data-init-01.json`.

| RAM slot | After 2.3.2.14 execution | After 2.4.0.24 execution |
| --- | --- | --- |
| UART2 handle 0x20000494 | 0 | 0 |
| UART2 pin table 0x20000498 | 0x434210 | 0x434220 |
| UART2 RX callback 0x200004A4 | 0 | 0 |
| UART2 awake 0x200004A8 | 0 | 0 |
| manager creation entry pointer 0x200004F8 | 0x42E6E5 | 0x42E6F5 |
| power callbacks 0x20026E44 / 0x20026E48 | 0 / 0 | 0 / 0 |

This resolves why pin table and manager function pointers were not found by simple byte search. Execution confirmed values produced by data initialization handlers; it does not fully specify the entire image's initial data format.

Old `0x432D04` conditionally executes data initialization and calls stock main `0x41B862` at `0x432D1A`. Stock main proceeds through several initializations after the init dispatcher and, from final `0x41B8BE`, reads and indirectly calls the pointer at `0x200004F8`. On a path retaining data initialization results, it connects to manager creation function `0x42E6E4`. Its actual entry is 0x42E6E4; intermediate halfword 0x42E6E8 is not used as entry.

Thus the static connection and initial data between initialization table and manager creation were confirmed. Whether intermediate functions reset that pointer, reset paths skipping data initialization, and scheduler/interrupt timing still require verification. UART handle is 0 immediately after data initialization, so successful handle registration by lower UART init remains necessary. These results do not remove recovery entry conditions.

## Continuing execution through UART handle registration

The 212-byte function at old `0x422E1C` / new `0x422E2C` registers the UART handle. It checks module<4 and output pointer, constructs a driver object at `0x20024400 + module*0x11C`, and writes it to the output pointer. UART2 is **0x20024638**. Original instructions also set the created object's identifier, module field, and other values. No direct peripheral MMIO access occurs inside the examined span of this function.

`tools/emulate_uart_init.py` starts with original data initialization and executes the full initialization loop at `0x41F612`. Handle registration, loop, and sleep wrapper run as original; only eight kinds of GPIO, IRQ, power, configure, control, and finalize callees are simulated. Power returns 0/7 were run for both versions. MMIO is not mapped, so unexpected access causes an emulator error. Results are outside Git as `uart-init-01.json`.

Both conditions confirmed UART2 handle=0x20024638, version-specific pin table pointer retained, RX callback=0, awake=0, and both power callbacks=0. Manager creation pointer was also retained. Handle object identifier, normal return, and stack restoration were checked.

Initialization returned 0 when power succeeded and 1 on failure. **Even on failure the handle remained, and examined slots looked the same as on the normal path.** A non-null handle and empty callbacks alone therefore cannot establish initialization success. Subsequent WAKE return and actual power status checks, plus cleanup, are necessary. This test does not cover other failure combinations or silicon power state.

Changes currently supported by evidence for a local 2.4 candidate are three hook positions, update-flag/handoff bindings, pin table address, append start location, and RAM recovery MRAM adapter address. A separate candidate retaining binary evidence for these addresses can be created, but must not be promoted to an installation profile without scheduler, watchdog, and physical recovery verification. Official support checks and the current web installation block remain in place.

Follow-up: a [2.4 local build candidate](bootloader-2-4-candidate.md) was generated and passed independent structural inspection and a rebuild under identical conditions. It is a research candidate, not an installation profile.
