# Diagnostic GPU ring consumption and guest framebuffer

bw-0259. **Original ARM submit function → ring → explicit diagnostic GPU model → guest screen buffer → PNG** was connected. Stock 2.4, stock 2.3, and Faceclaw38 all drew the same A in a 64×32 guest buffer. Unlike the earlier host reference image, these PNGs were extracted from guest RAM saved after Renode execution.

This is not natural full-main UI execution or 576×288 display integration. The list input was a 42-word batch collected in earlier original M55 render-function execution. Connecting generation and consumption from original draw through submit in one run is next.

## Allowed model scope

`BlackwallNemaReferenceGpu` is a separate diagnostic class, default enabled=false. Runner also requires explicit `--reference-gpu`; default path retains the existing passive sink. The main's general GPU model was not replaced.

This is neither full Nema ISA nor a physically verified GPU implementation. It supports only this profile:

- Synthetic nominal ring: virtual `0x2100b000`, physical `0x22000000`, first doorbell `0x22000014`, second `0x22000034`.
- Pinned list references and 42-word order, ROP `0x504`, CODEPTR `0x141f801f`, white, integer translation, A4 source.
- Source must be in pinned original main ROM range. A4 nibbles of actual used pixels allow **0 or 15 only**. Intermediate alpha, arbitrary background/color/shader are rejected.
- Black L8 destination 64×32, stride 64/80, in-range half-open clip. Sampling/L8 conversion assumptions match the [reference profile](nema-command-pixel-reference.md).

On first doorbell the model reads actual ring and list over the bus. Only after all source/profile/destination checks and temporary-frame creation does it use `SystemBus.WriteBytes` to write guest `0x2100a000`. No host-calculated expected-frame file is loaded into guest.

Second doorbell checks the observed packet for ID 8, IRQ request, and hold footer. **It records queued ID and IRQ request only; it does not create CLID update, NVIC interrupt, or successful original wait return.** All GPU reads also stop as unsupported. Subsequent commands beyond scope are not treated as successful.

## Actual results

13 native runs completed on pinned Renode 1.17 M55 image:

| Type | Runs | Confirmed |
| --- | ---: | --- |
| Nominal original submit | 3 | All three firmware images consume 42 words, one guest frame, original function returns |
| Clip/stride changes | 2 | Actual guest pixels match reference for clip `[13,20,18,27]`, stride 80 |
| Unsupported input | 7 | Rejection of disabled, shader, source range, intermediate alpha, nonzero destination, length, command order |
| Existing default-path regression | 1 | Without explicit opt-in, passive sink and no guest pixel writes |

All seven unsupported cases had frame bytes/consumed words/accepted doorbells/queued ID 0, and guest screen buffer unchanged from input. Original submission did not complete. Rejection occurs inside device before frame commit; CPU post-access watch hooks were not used as prior veto.

For five supported cases, actual RAM written by C# model matched independent Python reference byte-for-byte. **All WORK** matched previous passive submit runs except explicit initial input variations and framebuffer effects. Thus remaining original CPU submit results did not change with this device connection. SRAM, command list, ring, and surface canaries were preserved.

Separately from 13 native runs, **349 audit checks** passed for saved logs, input hashes, derived PNGs, guest pixels, memory ranges, and negative results. Seven Python reference units and compile passed. All 32 rows of three nominal, clip, and stride80 images were inspected. Work container was stopped.

## Verification limits

Original A in reference image uses only 0/255, so model is limited to binary A4. It does not claim intermediate alpha or arbitrarily establish actual GPU rounding. Half-open clip, integer sampling, synchronous processing, and fixed ring packet are diagnostic-profile assumptions.

Model validates each doorbell separately. If second footer is wrong after first list's frame commit, no atomic transaction rolls back the generated frame. Current success tests have both packets valid. Arbitrary ring cursors, wrap, multiple lists, and general hold semantics are unsupported.

Existing passive native result's zero guest surface differing from reference image was reused as red. The same passive native input was not rerun to create red. The first scenario-bundle invocation failed before native start because output parent was absent; it ran after parent creation. This was not firmware failure.

Full WORK impact checks for clip/stride80 were extended via saved audit after execution. Saved actual RAM was reverified without changing device/CPU runtime or repeating native only for verification.

## Reproduction and evidence

```sh
<venv-02>/bin/python tools/run_nema_submission_m55.py \
  <simulator> <nema-submission-contract-02> <new-private-output> --reference-gpu

# Run additional scenarios sequentially with new outputs on stock24:
# --case stock24 --reference-scenario clip|stride80|disabled|bad-shader|bad-source|
# intermediate-alpha|nonzero-destination|bad-length|bad-order
```

Source is `tools/renode-nema-reference-gpu.cs`; existing runner extension is `tools/run_nema_submission_m55.py`. Under the private simulator:

- `nema-ring-framebuffer-m55-01`: original code, inputs, C# model, setup, native logs, final RAM for three nominal cases.
- `nema-ring-framebuffer-scenarios-01`: explicit input-variation journals and nine scenarios.
- `nema-reference-passive-regression-01`: existing default behavior regression.
- `nema-ring-framebuffer-viewer-01`: BIN/PNG, figures, hash manifest made only from final guest RAM.
- `nema-ring-framebuffer-verification-01`: reused red, audit 349, source pins.

Next connect original draw functions through submit in the same M55 run to check command generation and pixel consumption without precompleted payload. Then address full-main display boundary and completion ID/IRQ/RTOS wait integration. Normal external font-bank, SPI boundary, and web installation/recovery conditions remain incomplete.

**Product 13/29=44.8%, scope v2 remain.** D3 requires full main, framebuffer, and 576×288 viewer integration; this 64×32 function test alone does not complete it. No glasses/case scan, connection, RAM execution, OTA, or persistent writes.
