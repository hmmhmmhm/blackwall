# Scope of GPU sampling sources and distinguishing inputs

Follow-up research to bw346. Original 102-word generation was verified in the [previous contract](gpu-packing-producer-contract.md). Here Think Silicon documentation distributed by ST was compared with pinned Apollo headers. **Evidence for format/filter settings increased, but Apollo's half-pixel rule or actual converted pixels were not verified.** GPU model and original main baseline were unchanged.

## Primary materials obtained

STMicroelectronics `x-cube-image-processing` commit `f415e9bcce92a532096a62f6d1e9764895bec95f` was pinned. Full tree has 25,563 entries, truncated=false. Git blob SHA-1 and downloaded SHA-256 were checked for four files:

- [NemaGFX API Manual](https://github.com/STMicroelectronics/x-cube-image-processing/blob/f415e9bcce92a532096a62f6d1e9764895bec95f/Middleware/NemaGFX/doc/NemaGFX_API_Manual.pdf), v1.4.17, 199 PDF pages. Page 20 distinguishes A4LE/L4LE as separate little-endian formats and describes AL44 as optional 8-bit format. This alone does not establish default A4 GPU nibble extraction or AL44 channel layout.
- [NemaVG1000 Public User Manual](https://github.com/STMicroelectronics/x-cube-image-processing/blob/f415e9bcce92a532096a62f6d1e9764895bec95f/Middleware/NemaGFX/doc/NemaVG1000_User_Manual_Public.pdf), v24.10.1, 138 PDF pages. Page 13 FSTRIDE distinguishes sampling modes 0/1 as point/bilinear. Page 56 names MATMULT bit 29 ADD_HALF. **This is a Nema pico VG1000 manual, not Apollo510B.**
- [image2header.py](https://github.com/STMicroelectronics/x-cube-image-processing/blob/f415e9bcce92a532096a62f6d1e9764895bec95f/Resources/images/image2header.py): no relevant packed-format conversion oracle was found.
- [NemaGFX distribution license](https://github.com/STMicroelectronics/x-cube-image-processing/blob/f415e9bcce92a532096a62f6d1e9764895bec95f/Middleware/NemaGFX/LICENSE.md): preserved with document distribution location. PDF has separate reproduction restrictions, so PDF, extracted text, and page images were not copied into Git.

Manual pages 13/56/57 and API page 20 were rendered as private PNGs. Page 56 bit diagram was visually checked to exclude text-extraction bit-position confusion. pypdf and PyMuPDF were used in private venv; exact versions are in report.

## Confirmed settings and assumptions not applied

Source FSTRIDE in three native lists is A4=`34000240`, L4=`35000240`, TEX2=`45000120`. Common filter/wrap fields are 0. Interpreted against public VG1000 register definitions, this is point/clamp; applying the same definitions to Apollo is an inference from cross-generation material. Original list field values and this interpretation are kept distinct.

Pinned Apollo `nema_programHW.h` names bit 29 `MMUL_DONTPLUS05=0x20000000`, opposite in naming polarity to VG1000 ADD_HALF description. Apollo behavior is not determined from either header name or other IP-generation manual alone. Current original list has MATMULT=0, so bit 29=0; whether fragment coordinates are already centered and where adjustment occurs relative to matrix remain unknown. The difference is not established as an actual hardware-revision difference.

Original CPU bitmap callback in earlier [font pixel reference](nema-command-pixel-reference.md) confirmed high-nibble-first. Pinned g2flash `845f665e0dfdcfd06b7d3a294388de6f17a5bd59` `patches/draw.c:set_pixel4` writes even x to high nibble, and `zlib_glue.c:display_copy_hook` copies that shadow to panel buffer. This is **the layout adopted by upstream CFW code**, not independently verified current Faceclaw38 binary, stock GPU sampler, or physical display.

## Distinguishing inputs for next test

Private verifier computed eight combinations of these three choices for input row `13 27 49 6b 8d af c1 e5`:

- Half-pixel input-coordinate adjustment present/absent.
- Source high/low nibble first.
- Alpha high/low nibble in AL44.

The row gives distinct virtual outputs for all eight combinations, distinguishing these hypotheses. This is **test-input design calculation**; no output was registered as correct or as executed shader result. Identical adjacent white/black bytes cannot distinguish them. Actual verification also needs row padding, boundary clamp, source coordinates after clip, nonzero destination, and quantization controls.

Next implementation/verification must use inputs exposing these differences. Separate actual shader semantics from unverified reference sampling policy and retain default strict rejection. Do not remove existing rejection or copy host-expected results to guest RAM merely because another IP document was found. GPU work completion/natural main return boundary remains bw348 in the [roadmap](../../architecture/emulator-roadmap.md).

## Reverification material

Outside Git, `simulator/gpu-sampling-research-01/` preserves tree/commit pins, sources.json, PDFs, extracted text, page PNGs, CFW source pins, `verify-research.py`, and `verification-report.json`. Verifier checks Git blob/SHA256 of four downloads, document pages/fields, previous three native packet hashes/fields, and distinguishability of eight hypotheses. No new firmware/native execution or hardware access. Current GPU consumer/adapter/strict/runner unchanged. Overall 3/16, API checklist 3/6; sampling and full UI/natural main incomplete.
