# First dashboard frame from original main

bw479, 2026-11-15. **From stock 2.4 original ARM main reset through virtual touch, UI, drawing, and display conversion, a 576×288 dashboard was obtained.** Clock, date, status, and `No news available / Add new sources in the app` were visually confirmed. It meets E09 first-screen condition under the declared functional board profile. Full boot, continuous screen, and the same execution on other firmware are not yet complete.

## Execution and pixel provenance

Original reset → IOM5/GPIO27 touch → original app 1 request → virtual UART peer reply → original UI callback/layout → original renderer/glyph → Nema submission → GPU functional-model guest RAM writes → original display-conversion list completion → L8 source capture.

- Main SHA256: `df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a`.
- Instructions, branches, returns, PC, and TCB were not forcibly changed and no API test caller inserted. Actual execution script was checked for absence of CPU-control writes and for main hash.
- Full SRAM at initial `before-input`, `after-input`, and `before-reply` was byte-identical to existing pinned baseline. This does not guarantee all observation configurations are always noninterfering.
- Original glyph calls 44, GPU accepted lists 31, draws 120. List/draw counts are not frame counts. GPU rejections, all strict guards, CFSR/HFSR, and memory-policy violations were 0.
- Of three completed display-conversion captures, first two were blank. First content-bearing source was address `0x201299e0`, 576×288/165888 bytes, 5553 nonzero pixels.
- At first fade-in actual values are 0..13. **Raw was preserved unchanged; only viewing image and viewer brightness were set to 16×.** Screen SHA256 is `5bed2a24ac17aa73a627552376d35af5c27988fd57e60e12faa7c29b55403501`.
- Machine virtual time at capture end was 8.621994 seconds. Existing 10→167 MIPS interval profile was used; this is not physical boot-time or FPS measurement.

Distinguish final 320×480 internal cache from 576×288 HUD. Pixels are guest surface produced by device backend processing original draw commands and ROM glyphs/images, not a host-prepared screen. Capture reads the source completed by original packing list. It is not expanded to physical MSPI/panel display success.

## Functional-model boundaries

A separate profile was used under user approval not to make full physical sensor/GPU reproduction a prerequisite for first screen. Follow [implementation and failure boundaries](screen-first-functional-profile.md).

- GAF requests 2/4 complete under actual control/trigger/virtual-time contract. EDMP ROM and fusion math do not execute. Assumptions including cold accuracy 0 and nominal clock correction 1 are declared. Readback of RAM bytes uploaded by original code is supplied unchanged.
- Original FIFO configuration is connected to existing shared-register/transport model. Full natural lifetime of actual samples/GPIO38 consumption is separate.
- IOM2 OPT3007 candidate was compared with address, ID, and transfer format in [TI SBOS864](https://www.ti.com/lit/ds/symlink/opt3007.pdf) and original requests. Current virtual environment is 100 lux/immediate conversion, not physical identification of installed chip or optical response.
- GPU handles declared grayscale/alpha, A4/L4/L8, packing reference rules, and limited shader patterns. This is not actual GPU ISA execution or verification of filter/quantization/MSAA agreement. Filtered images support only observed integer-translation conditions.
- Retention preparation reuses bw416/417 model. Original WFI remains; no hardware guarantee of actual power loss/RAM retention.

Actual glasses/case access, flash, OTA, persistent writes, Astra, and external publication: 0.

## Reproduction and verification material

`tools/run_screen_first_native.py <new private simulator path>` checks pinned baseline SHAs. `tools/audit_screen_first_native.py <capture> <new audit path>` checks main, model, initial SRAM, original UI boundaries, faults, and completed source pixels and creates local HTML/PNG viewer.

- Positive: `private:simulator/screen-first-native-23`.
- Audit/viewer: `private:simulator/screen-first-acceptance-01` `report.json`, `index.html`, `screen-raw.png`, `screen-gain-16.png`.
- Full manifest: `private:simulator/screen-first-functional-manifest.json`.
- Three semantic negatives—zero screen, changed main, and script with CPU seed—were rejected without a new VM.
- Functional checks: GAF 109, OPT3007 33, normal sleep regression 23, GPU packing 1539/texture 459. Existing three-original shape/quad replay and rejection regression 996000 also passed. These counts are not boot runs or progress percentages.
- Absence of 54 owned containers from this work was confirmed. Failed/unsupported native01–22 and unit failure evidence was preserved and not counted as success. Native22's `Sat 1` was a partial frame.

Next verify original service/task wait/resume, boot lifetime, and continuous frames after first screen under the same functional profile. Extend natural screen and reset lifetime to other originals afterwards.
