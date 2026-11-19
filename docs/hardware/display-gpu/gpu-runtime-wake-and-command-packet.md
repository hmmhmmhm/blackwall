# GPU runtime wake and original command packet

Latest status follows the [quad coverage contract](gpu-quad-coverage-contract.md). Across three originals in the reference profile, 14 lists/142 draws, 12 completions, and ID 3 were confirmed; the next 102-word texture submission is the current boundary. Default strict rejects quads. The no-consumer/108-word/252-word boundaries below are historical checkpoints; full UI and natural main remain incomplete.

bw-0346, E05/E09. **Original render tasks in stock 2.4, stock 2.3, and Faceclaw38 requested GPU reactivation/initialization, created a 24-word command list and ring header, and wrote the doorbell.** The virtual GPU did not consume it. Doorbell was rejected at an unsupported boundary; submission return, completion IRQ, and pixel output remained incomplete.

## Cause and model change

The first draw in [bw345](jbd-display-status-and-render-task.md) stopped at LDO request `0x40020080 ← 0x6d3d9`. The existing model permanently retired the power epoch after the initial 18-step GPU preparation/on/off sequence. Original Nema render path later requests power-on again.

Opt-in `gpuRuntimeWakeResponse` was added. Default `-1` rejects reactivation as before; `1` is virtual on response, `0` virtual stuck-off. Neither is a measurement of actual voltage or settling delay.

A new cycle starts only when all hold:

- Prior GPU off response and 18 off stages completed.
- Buck, GFX selection/request, MCU mode, and HFRC are ready.
- First write exactly matches original CORE LDO low ten bits `min(current+12,1023)` and preserves neighboring bits.

Only after validation are preparation/off/power states transitioned to a new epoch. Existing 18-stage preparation and off contracts are reused; GPU enable before preparation is not allowed. GPU ID/ring/reset/raster epoch state requires new initialization. Lifetime counters are distinct from epoch identity/interrupt counters. This virtual profile does not certify every physical register-retention behavior.

## Distinguishing boot and reinitialization order

After first native extension, GPU ID and completion ID caused consecutive blocks. Their common premise was that boot-observed order was mandatory at runtime. Instead of continuing to allow subsequent addresses one at a time, the full original Nema initialization order was rechecked:

`GPU ID read → completion ID 0 write → ring request/base/size → command/GPU reset → raster initialization`

Stock 2.4 Nema initialization is `0x4d2df4`, stock 2.3/Faceclaw38 `0x4c5444`. Order was verified in three originals; recheck method is preserved in private `gpu-runtime-wake-research-01/verify-init-order.py`. In a new epoch, GPU ID read before ring and completion ID initialization before IRQ clear are supported while power is on. Existing ID-response profile remains.

Readback of firmware-written completion ID 0 is also supported. **No feature increments completion ID as though GPU work were processed.** There is currently no command consumer and subsequent doorbell remains rejected. Initial register readback is distinct from completion of submitted work.

## Evidence from actual original execution

Existing API diagnosis conditions remain: main reset → pause before IMU getter → insert explicit caller. Original main images/branches/callee returns and UI/Display/renderer PC/TCB/stack/mode were unchanged. Only JBD component and two GPU lifecycle components were replaced in parent strict model; saved audit compared all bytes.

All three normal images:

- Actual `ambiqdraw` task called draw, target setup, submit, and ring-submit functions.
- Completed runtime preparation 18 stages and on response, ring three stages, reset two stages.
- Guest SRAM packet was `[0xf0, list-address, 0x200f4, 24]`. List address/length matched actual first arguments of original ring function.
- Original ARM code created 24 command words in guest SRAM. CPU test caller did not precreate a frame or command list.
- Stopped at doorbell `0x400900ec` write. Stock 2.4 store PC `0x560f68`; stock 2.3/Faceclaw38 `0x530054`.

Entering submission differs from GPU accepting/completing it. `submit_observed=true` is call observation, accompanied by `submit_completed=false`, `gpu_work_consumed=false`, `frame_pixels_verified=false`. Packet checks cover header, RAM range, arguments, and command-byte hash, not yet GPU opcode/ROP semantics.

Native `response=0` control remained `stuck-off`, status 0, with zero ring-submit calls. This is incomplete behavior within the observation interval, not completed original timeout handling or full error recovery. `post_mode1_supported` likewise means no unsupported access in that interval, not full support.

## Verification and reproduction

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/run_display_activation_m55.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-capture-outside-Git> --case stock24 --trace-content \
  --jbd-status-hex 5a01 --gpu-runtime-wake-response 1
```

`stock23`, `cfw`, and `--gpu-runtime-wake-response 0` are supported. Existing `--audit-existing --audit-output <new-audit-folder>` checks without rerunning. Schema 2 distinguishes execution from state-contract judgment. Passing this contract does not satisfy natural main, GPU consumption, or screen acceptance.

Private `simulator/gpu-runtime-integration-verification-01/manifest.json` pins three normal/one incomplete native captures, saved reaudits of three prior LDO-block baselines, and 15 state/preparation/packet-header/component mutations. Candidate and baseline have different observation recipes, so CPU/event exact equivalence is not claimed.

`tools/verify_gpu_runtime_wake.py` uses an existing synthetic boot fixture, separate from actual main testing:

- 157 normal checks: three repeated cycles, upper trim, neighboring-bit preservation, rejection of wrong first request/order, unready clock, incomplete off, restart while on, initialization order and latch readback, global reset.
- Three default-disabled and 29 stuck-off checks; total 189.
- Boundary trim seed was injected by reflection only in synthetic units. Native capture LDO/TCB/frame values were not host-injected.

Missing new constructor, synthetic seed internal-setter access error, and initial order/completion-ID readback failures were preserved as red material. Native stock24-01/02/03 ID/completion-ID blocks are intermediate diagnosis; final same-component comparison uses 04 and final stock23/CFW captures. Aborted machines were not resumed.

## Next work

Use captured actual packets/lists to connect GPU command consumption, framebuffer writes, and completion ID/IRQ. Do not apply the existing reference GPU's fixed-address 64×32/A4-only profile unchanged to full main. Specify supported opcodes/state/colors/ranges and validation before failure, and check whether actual guest commands generate pixels. Do not copy expected screens from host or force waits to succeed.

Overall 3/16=18.75% and first-screen checklist including API 3/6=50.0% remain. M3 frame preparation and M5/M6 pixels/reproduction remain incomplete. No physical-device access or writes.

## bw346 resumption design: actual ring consumer

Extend a functional model within existing approval. Extending fixed 64×32 diagnostic GPU cannot reflect actual ring addresses, stride, and clip; a full GPU ISA exceeds current need and evidence. Select a limited functional consumer validating/preserving original ring's initial IMEM/register writes and consuming supported commands at actual list address/length. Do not unconditionally succeed CPU-written completion IDs; only processed footers update completion.

First supported command is current original 24-word opaque binary solid L8 rectangle profile. MATMULT=0x90000000 matches public header MMUL_BYPASS|MMUL_NONPERSP. Opcode100 value 2 and CODEPTR/IMEM combination are limited to observed profile, not interpretation of full shader ISA. Read dynamic destination, resolution, stride, draw/clip and preserve out-of-bounds/padding. Half-open rectangle/clip is an explicit functional-model contract, not physical raster accuracy certification.

Only after all ring/list/opcode/address/profile validation apply DMA, cursor, and completion state. Reject unsupported opcodes/colors/IMEM changes, ranges, and overlap before side effects. First replay saved actual ring/list from three originals in the same C# consumer and test address/stride/clip variations and negatives. Saved replay is not evidence of live original RTOS GPU submission completion or natural main screen; then connect the same consumer at Renode peripheral boundary.

## bw346 resumption result: first clear/completion IRQ and second submit

`nema-ring-consumer.cs` is a C# functional consumer separate from Renode; `renode-nema-ring-device.cs` connects it to existing strict GPU ring configuration, power epoch, completion ID, and IRQ boundary. Defaults remain unchanged; enabled only by `--gpu-ring-consumer`. It validates initial IMEM/register 88 words and reads destination, stride, size, draw/clip, and color from actual list address/24 words. Only opaque black/white L8 rectangles are supported, not full shader/line/texture ISA.

DMA, cursor, and completion state apply only after all guest input validation. Reject list/ring overlap with destination, unsupported commands/colors/stride/clip/ranges, and bad completion/hold footers. Overlapping draws within a single doorbell and ring wrap remain unsupported. GPU power-off with incomplete work is also rejected. Functional-profile limits are not generalized as physical GPU valid-input limits.

Two discovered errors were corrected. Original footer's last value is 4864, not 0. Three original footer emitters' instructions reading ring table+16 and recording it were confirmed, and red→green test rejecting incorrect 0 preserved. Also original code powers GPU off and on after first work, so completion ID 0 and first work's lifetime completion history were separated at epoch reset. Current ID 0 does not mean no previous completion; global reset initializes both.

Final same-model captures: private `gpu-ring-native-stock24-04`, `gpu-ring-native-stock23-01`, `gpu-ring-native-cfw-01`. Original main bytes remain unchanged and API caller insertion/observation-recipe limits remain. All three:

- Consumed one actual original-written 24-word list and filled 576×288 L8 area, 165,888 pixels, black. Host did not prewrite command or expected screen. This is not evidence of nonzero UI screen.
- Consumed actual original-written subsequent footer, producing completion ID 1 and one IRQ assertion; original CPU acknowledged IRQ once. Completion was not substituted by wait stub or host semaphore write. These counts alone do not establish verification of original waiter's entire path.
- Original draw/target/submit each reached two calls and GPU runtime epoch 2 began. A 108-word list then arrived and was rejected at supported-length boundary. No pixels, completion ID, or IRQ were generated for that second list.
- Current epoch completion ID is 0; lifetime last completion ID is 1. Report `post_mode1_supported=false` includes consumer support rejection. Guard count 0 alone does not establish full support.

The 108 words contain multiple draw-start/end and opcode100 value 1 after initial solid state. Some coordinates lie outside 576×288 viewport and relate to 640×480-family shapes created by existing callback. Next identify rectangle/line and clip semantics from original emitter/public API and extend state stream. Do not treat value 1 as rectangle without meaning verification.

Verification material:

- `gpu-ring-consumer-green-03/report.json`: 252 checks replaying saved ring/list of three originals, address/stride/clip, padding/neighbors, rejection without DMA/completion for invalid opcode/range/color/footer and trailing packet. Saved replay is not CPU execution.
- `gpu-ring-footer-source-01/report.json`: footer-store instructions in three originals and 4864-byte field confirmed.
- `gpu-ring-integration-verification-01/manifest.json`: final three native, saved audits of three no-consumer baselines, two zero-consumption semantic controls, one component-mutation rejection. Full frame/natural main completion false.
- `gpu-ring-runtime-regression-{normal,disabled,stuck}-01/report.json`: current strict model passes existing epoch/initialization 157, default-disabled 3, stuck 29. Profile without new consumer remains. Public CLI CFW saved audit also passed in `gpu-ring-cli-saved-audit-01`.

Intermediate runs remain. After host .NET10 CoreCLR error in `gpu-ring-consumer-red-01`, pinned Renode environment was used. Red02–04 are dynamic C# type discovery errors, red05 actual unimplemented-consumer error. First native01 had telemetry-node lookup error, native02 incorrect footer-0 assumption, native03 loss of lifetime count after epoch reset. They are not mixed with final native04/stock23/CFW as passes.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/run_display_activation_m55.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-capture-outside-Git> --case stock24 --trace-content \
  --jbd-status-hex 5a01 --gpu-runtime-wake-response 1 --gpu-ring-consumer
```

The same CLI's `--audit-existing --audit-output <new-audit-folder>` verifies saved component hashes and reuses old evidence without new native execution. Overall 3/16=18.75%, supplementary 3/6=50% remain; M5 is partial with only first clear confirmed. Next 108 words, nonzero UI, full frame, and natural input remain incomplete.
