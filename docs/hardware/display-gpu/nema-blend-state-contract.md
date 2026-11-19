# Original Nema blend path and SRAM state contract

bw-0256. **The earlier 2.4 50-word shader path was caused by missing standalone-test SRAM, not a version-specific difference.** After collecting and restoring original main state, stock 2.4, stock 2.3, and Faceclaw38 all generated and returned a 42-word batch on Renode M55. This is not yet GPU pixel execution.

## Cause and correction

Existing font fixture restored 24 KiB of original low SRAM and a specific high SRAM handler, filling the remainder with 0. Nema global state at `0x20005370` in older versions was within the collected range, but 2.4's `0x200076c8` was outside. The problem was treating initialized original state and fixture zero as equivalent.

Original blend core reads the first byte of this area to select ROP path. It was 0 in old 2.4 fixture and 1 in older versions. Agreement of two CPU engines' generated commands for identical input did not prove input completeness.

New `nema-capability-candidate.json` reruns original main from existing `em9305-reset-main-01` unchanged. Existing peripherals, board, branches, and execution observer are unchanged; after stopping at existing strict boundary, it reads 64 bytes each from two candidate SRAM regions. All three cases exactly matched baseline CPU, instruction count, observation state, and full events and passed schema2 semantic checks.

| Input | Original blend core | Global area | Original main first word | Next main boundary |
| --- | --- | --- | ---: | --- |
| Stock 2.4 | `0x560840` | `0x200076c8` | 1 | `0x58253a` DCX write |
| Stock 2.3 | `0x52f92c` | `0x20005370` | 1 | `0x57b1e2` DCX write |
| Faceclaw38 | `0x52f92c` | `0x20005370` | 1 | `0x57b1e2` DCX write |

This state is created by original main in the current simulator using an explicit GPU config response, not measured physical GPU capability. Existing main-model limitations including touch and missing-font-asset diagnosis remain.

## Correspondence between original functions and public API

Actual helper calls proceed unit wrapper → state-cache wrapper → Nema blend core. Read-only code-hook observation at original core entry showed identical arguments for all three:

```text
R0=0x504, R1=0, R2=1, R3=0xffffffff
```

These correspond to pinned LVGL Nema header `nema_set_blend(mode, dst_tex, fg_tex, bg_tex)` and `nema_set_blend_blit()` argument construction. TEX0=0, TEX1=1, NOTEX=-1. This path can therefore be described as SIMPLE factor combination, destination TEX0 / foreground TEX1 / no separate background texture. It does not mean original firmware symbol names were recovered.

Original ROP writer was also confirmed to emit mode to register `R0=0x1d0`. Canonical batch prefix in all three:

```text
ROPBLENDER_BLEND_MODE = 0x504
MATMULT              = 0
CODEPTR              = 0x141f801f
```

`0x504` is SRCALPHA / INVSRCALPHA factor, distinct from SRC_OVER `0x501`. Actual channel conversion, sampling, and rounding for current TEX1=A4, TEX0=L8, white input cannot be established by CPU commands alone. CODEPTR packed fields and built-in shader meaning also remain unconfirmed.

## Restoration and execution controls

`prepare_nema_state_captures.py` validates original raw hash/pinned main material, native-log diagnostics/stopped state, and input snapshot hash. It restores the 64 bytes read from original main only at the relevant address, creating new inputs without modifying existing captures.

- In 2.4, 23 of 64 bytes differed. Older and CFW changed 0 bytes.
- Auxiliary M7 compared canonical-area restore / historical area / first-byte-only restore / observer off across three inputs: 12 batches, 60 upper original function calls, not internal call count.
- **In 2.4, restoring only first byte yielded canonical 42 words.** Historical input yielded 50; older/CFW yielded 42 both ways.
- Final WORK hashes matched with observation hook on/off. No memory-write hook used; absence of all transient writes is not claimed.
- SRAM was guest read-only; source bitmap, output surface, and guards were unchanged.
- On M55, an ARM test caller also executed five original functions in sequence; all three inputs yielded 42 words, END marker, and normal return. Lists matched M7 reference byte-for-byte. This is not a natural original-main UI frame.

## Prevention and verification

New batch preparation and M55 batch replay require `validate_region`. Missing collected-region metadata, source-hash mutation, and actual SRAM-region mutation were rejected in all three cases. Historical `50/42/42` material is preserved and distinguished as results of prior inputs.

Separate from three native main runs and three M55 batch runs, 81 saved-material/original-function audit checks passed. Python compile passed. Changes added after native execution were host preflight checks; saved native runner/preparer and remaining code were confirmed identical. GPU model, ARM caller, and guest code were unchanged. No execution container remained.

Current reproduction sequence:

```sh
python tools/prepare_nema_state_captures.py <simulator> <original-glyph-captures> <new-state-captures>
python tools/prepare_draw_command_batch.py <simulator> <new-state-captures> <new-batch-inputs>
python tools/run_ambiq_glyph_m55.py <simulator> <new-batch-inputs> <new-m55-output> --kind full-letter --canonical-itcm
```

Python uses private `venv-02` with Unicorn and Capstone. Pinned main-collection source is already obtained `nema-capability-main-01`. These paths are not commands to overwrite existing outputs. Do not repeat native when reusing pinned main source.

Evidence is outside Git in simulator `nema-capability-main-01`, `nema-state-captures-01`, `nema-state-batch-inputs-01`, `nema-state-batch-m55-01`, and `nema-blend-contract-verification-01`. Last folder's `audit.py/report.json`, `canonical-profiles.json`, and `source-pins.json` record controls and source versions.

## Next connection

Since observed fragment upload is unnecessary on current canonical glyph path, there is less reason to make general shader ISA implementation a prerequisite. Next distinguish actual semantics and remaining assumptions for A4 sampling, L8 conversion, ROP factors, and clip coverage. Then define functional model scope for accepting original commands and updating framebuffer. Do not make unsupported paths succeed with arbitrary pixels/completion IRQ.

Original main SPI boundary and external font-bank, GPU submission/completion/framebuffer/viewer, and web installation/recovery integration remain incomplete. Product 13/29=44.8%, scope v2 remain; no physical access or persistent writes.
