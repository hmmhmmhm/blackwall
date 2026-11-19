# Original shape-command stream and first nonzero virtual screen

Follow-up: [quad coverage contract](gpu-quad-coverage-contract.md). Explicit reference profile advanced through 14 lists/142 draws and 12 completions; current boundary is 102-word texture submission. The 252-word boundary below is this document's historical result.

bw346 resumed, 2026-11-13. In API diagnosis of original stock 2.4, stock 2.3, and Faceclaw38, 11 actual guest command lists, 106 shapes, and 11 completion IRQ assertions/acknowledgements were processed per image. Nine white dots appeared in the 576×288 L8 screen read from actual guest SRAM, with identical pixels across images. Full UI processing stopped at unsupported curve command in subsequent 252 words. Natural main remained at IMU getter boundary; diagnosis included test-caller insertion.

## Changed execution boundary

[Prior result](gpu-runtime-wake-and-command-packet.md) rejected second 108-word list on length after first 24-word clear. Here existing C# consumer was extended to a state stream:

- Interpret destination, L8 stride/resolution, clip, shader profile, color, and start/end registers, retaining state between draws.
- Handle integer rectangles with command value 2 and horizontal/vertical lines with value 1. Clip negative/outside-viewport coordinates to clip and surface bounds.
- Composite multiple draws on same surface in order in a private work buffer. Apply actual guest RAM and state only after full doorbell validation.
- Reject invalid opcode, diagonal lines, shader/color, address overlap, changed surface layout, and incorrect footer. Pixel work is bounded per doorbell.
- Preserve final surface read from actual bus RAM as separate binary. Last capture and lifetime completion history survive power-epoch changes; global reset clears them.

Rectangles exclude end coordinates; axis lines include both endpoints. Line rule is a chosen **functional-model contract** based on original rounded-rectangle symmetric boundary calculations, not physical GPU raster/AA accuracy verification. Diagonal lines, textures, general shaders, and curves/AA are not automatically approximated. Initial IMEM profile and binary opaque solid L8 restriction remain.

## Original code evidence

`verify_nema_ring_consumer.py --shape-streams` runs original bind/reserve and rectangle/rounded-rectangle emitters in auxiliary Unicorn Cortex-M7 context. Main image is read/execute-only; no hooks, MMIO, or GPU execution. Nema state and command buffer are explicit synthetic inputs.

For all three originals, actual ARM emitter output of 90 words for `x=1,y=1,w=638,h=478,r=7` exactly matched shape portion following state setup in native 108-word list. Packing of negative starting coordinates and controls producing no commands for width/height 0 were also confirmed. This evidences emitters, not full main boot or physical pixels. Register/MMUL names follow [pinned SDK sources](../../data/gpu-extension-upstream-snapshot.json) and `NOTICE.md`.

## Actual M55 results and pixels

Final captures outside Git: `simulator/gpu-shape-native-stock24-01`, `gpu-shape-native-stock23-01`, `gpu-shape-native-cfw-02`. All three use the same model.

| Observation | Per-image result |
| --- | ---: |
| Lists / words consumed | 11 / 834 |
| Shape draws / pixel-write operations | 106 / 331,585 |
| Completion / IRQ assert / original CPU ack | 11 / 11 / 11 |
| Power epoch / current completion ID | 12 / 0 |
| Nonzero pixels / connected components | 684 / 9 |
| Next unsupported list | 252 words, including register 0x120 / command value 0x02800005 |

331,585 counts pixel-write operations including duplicate locations; it differs from 684 final nonzero pixels. Last completion ID 1 is distinct from epoch 12's current ID 0. Even if beginning of next list is prepared in private buffer, unsupported 0x120 does not apply actual DMA/completion.

Actual `gpu-last-frame.bin` was byte-identical to corresponding final guest SRAM surface. Screen has nine white dots each 76 pixels with 10×10 bounding box. x ranges 84–93 / 284–293 / 484–493, y ranges 39–48 / 139–148 / 239–248. PNG generated from actual binary was visually checked; host did not copy an expected picture. Frame SHA-256 across three images: `289cde09202715f253c6732974fe6f8d9b2209685f1a77b65f6dfa27f75b484a`.

Original frame-wrapper completion was not reached. Existing `frame_pixels_verified=false` and new `actual_guest_surface_verified=true` refer respectively to full UI/frame acceptance and actual pixel evidence for partial surface. M5 partial, overall 3/16 and supplementary 3/6 remain. Synthetic caller is not promoted to natural-main completion.

## Verification and reproduction

Private `gpu-shape-stream-green-02` preserves existing 24-word tests and actual 108-word black/white variants, clip/neighbor preservation for every pixel, state order, reverse/negative axis lines, points, and diagonal rejection. Report's 995,745 includes per-pixel assertions, not independent scenarios or product completion rate. Overall progress is not raised by this number.

`gpu-shape-integration-verification-01/manifest.json` checks three native captures, saved audits of three prior first-clear baselines, two zero-consumption controls, three rejections for surface truncation/stride/model mutation, actual frame/memory match and nine components, and current source/model hashes. Core lifecycle source matched earlier verification, so 189 checks were reused by hash without rerun. Public CFW saved audit passed in `gpu-shape-cli-saved-audit-01`.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/verify_nema_ring_consumer.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-private-output> --shape-streams
```

Native execution uses existing display runner with `--trace-content --jbd-status-hex 5a01 --gpu-runtime-wake-response 1 --gpu-ring-consumer`. Saved audit uses same CLI's `--audit-existing --audit-output`. Proprietary captures, frames, and original images remain outside Git.

First red reproduced existing consumer's 108-word rejection. First CFW native01 was interrupted by insufficient disk and Docker connection loss and excluded from completion evidence. After [space recovery](../../architecture/simulator-asset-storage.md), tool environment and remaining containers were checked before new CFW02 run; it was not restarted merely on timeout.

## Next work

Investigate vertex registers 0x120–0x154 and 0x02800005 in current 252 words against original emitters and public definitions. Do not replace fixed-point vertices and curve/coverage with lines or rectangles without establishing their meaning. After connecting full UI frame and failure controls, return to natural initialization and device/transport input. Physical GPU, boot, and flash verification were outside this work.
