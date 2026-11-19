# Original draw, submit, and guest pixels in one M55 run

Follow-up bw264 added [actual NVIC IRQ28 and original completion handling](nema-native-irq-completion.md). Below is bw260's historical execution without IRQ.

bw-0260. **Without preloading a command list, lists created by original ARM draw functions were directly connected to original submit function and diagnostic GPU consumption.** A from stock 2.4, stock 2.3, and Faceclaw38 and W from stock 2.4 appeared in guest 64×32 buffers.

This path starts from a synthetic function-test caller. It is not natural boot from original main reset through UI, a full actual GPU specification implementation, or 576×288 display integration.

## What was not preloaded

Input command buffer's 4096 bytes are all `0xa5`, descriptor used words 0. This was confirmed in pre-execution hash and actual binary. Unlike earlier [completed payload submission test](nema-reference-ring-framebuffer.md), draw commands used by GPU must therefore be generated during this run.

`nema_live_draw.py` verifies pinned draw inputs, original main hash, and canonical Nema state, then combines only previously declared synthetic 20-byte ring table, ring storage, and descriptor. Host does not place bitmaps, commands, or completed frames in guest. Original ROM bitmap remains mapped unchanged.

Unit/layer/context, surface/ring addresses, function arguments, and ABI/FPU initial state are function-test inputs. Full SRAM, scheduler, and physical GPU are not claimed restored. Original bitmap's address `0x10` read uses actual LOAD and limited guard from existing [ITCM contract](glyph-itcm-read-contract.md). No physical verification of the value or branch skipping.

## Actual execution sequence

Existing ARM test caller was extended to six calls. It only passes arguments, BLX to original entries, and stores progress after actual returns. Drawing, glyph interpretation, and command generation were not reimplemented.

| Original call | Used words after actual return |
| --- | ---: |
| list bind | 0 |
| destination texture bind | 6 |
| clip | 10 |
| generic letter | 42 |
| list unbind | 42 |
| list submit | 42 |

Original descriptor/bitmap/reshape/Ambiq helper path inside generic letter determines actual glyph and texture address. After submission, diagnostic GPU reads ring, 42-word list, and original ROM glyph from the same guest RAM and writes guest surface. END marker and poison area after commands were also checked.

Each native run has one StartAll and one final Pause. No host PC changes, return substitutions, or intermediate pauses between functions. Test start PC is synthetic caller `0x2100e000`; PCs/branches inside original functions were not manipulated. Six markers are recorded only after actual BLX returns. All SP and callee-saved registers preserved.

## Control results

Eight native runs:

- **Three passive controls:** three firmware images execute six original functions from empty buffer, create list, and submit. No GPU execution, so screen remains 0.
- **Three diagnostic GPU A runs:** A appears in guest under same conditions. All WORK except screen buffer matches each corresponding passive control.
- **One W run:** changing function argument to 87 made original code create W glyph commands; actual guest pixels matched original CPU bitmap callback for W. Model does not output a fixed A.
- **One omitted-letter run:** only letter call omitted from synthetic test caller. Bind/destination/clip/unbind actually returned, but list had only ten words. Device rejected submission and no submit-return marker appeared. Pixels, accepted doorbells, consumed words, and frame writes were 0. This is a negative caller test, not an original firmware branch patch.

In four successful cases, original descriptor/bitmap callbacks were separately executed eight times total for expected coverage. Actual guest crop matched callback output and prior pinned glyph hash. A is 11×16, W 13×16, draw origin `[10,16]`.

Existing five-call caller was recompiled and confirmed byte-identical to existing binary; no firmware native rerun for that regression. **348 saved-audit checks** verified actual logs, input/final hashes, caller ELF/bin/BLX, initial poison, return markers, pixels, and PNGs. Images were extracted from final guest RAM and all 32 rows visually checked. Execution containers stopped.

## Still incomplete

Diagnostic GPU uses previously declared binary A4/white/black L8/integer-translation profile. General shaders, intermediate alpha, multiple lists, and arbitrary ring wrap are unsupported. **Observed queued ID 8 is not GPU completion ID update.** IRQ, RTOS semaphore, and successful original wait were neither generated nor returned in their place.

Next investigate original completion ID/IRQ handler and semaphore wait contract. A guest frame alone does not establish that main normally proceeds to next UI work. Full-main SPI/external font-bank issues, 576×288 viewer, and web installation/recovery integration remain.

## Artifacts

Source: bounded caller extensions in `tools/nema_live_draw.py`, `tools/run_nema_submission_m55.py`, `tools/run_ambiq_glyph_m55.py`.

Simulator outside Git:

- `nema-live-draw-passive-01`: three passive cases.
- `nema-live-draw-framebuffer-01`: command generation/submission/pixels in same run for three A cases.
- `nema-live-draw-w-01`, `nema-live-draw-no-letter-01`: glyph-change/omission controls.
- `nema-live-draw-five-call-regression-01`: existing caller compile regression.
- `nema-live-draw-viewer-01`: PNGs extracted from actual guest RAM and manifest.
- `nema-live-draw-verification-01`: audit 348, source pins, PNG decode material.

```sh
# New private outputs for each. Obtain three passive controls once before diagnostic GPU controls.
<venv-02>/bin/python tools/run_nema_submission_m55.py \
  <simulator> <nema-submission-contract-02> <new-passive-output> --live-draw

<venv-02>/bin/python tools/run_nema_submission_m55.py \
  <simulator> <nema-submission-contract-02> <new-output> --live-draw --reference-gpu
# Variations: --case stock24 --character 87 / --case stock24 --omit-letter
```

Current runner's A-control source is pinned `nema-live-draw-passive-01`. Existing material is reused; do not overwrite it. Pillow for verification used system Python, ARM analysis existing venv. No new package installed.

**Product 13/29=44.8%, scope v2 remain.** D3's full-main/576×288 criterion is not yet met. No physical scan/connection/RAM execution/OTA/persistent writes.
