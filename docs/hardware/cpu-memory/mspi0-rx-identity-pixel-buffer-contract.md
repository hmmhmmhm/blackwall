# MSPI0 Diagnostic RX and Original Pixel Buffer

bw-0318. Analyzed bw317's three saved main/SRAM/GPR inputs and original ARM without a new native main run or peripheral-model change. A PNG confirmed a **nonzero pixel test pattern** written by the original rectangle callback. This was an isolated function-call test, not successful natural M55 main UI or physical panel output.

## RX 9f is not an ID authentication check in this call

The request is instruction=`9f`, RX four bytes, CTRL=`40441`. Original HAL waits for data in RXENTRIES, reads a 32-bit word from RXFIFO and stores it in the caller buffer, then waits for controller completion. After success or failure, IRQ clear-all and restoration of prior INTEN=`1a80` were confirmed.

The four response bytes reach memory in their original order from the little-endian FIFO word. In a completion-timeout fixture, already received data remains in the buffer and result 4 is returned. A FIFO-empty timeout-0 fixture returns 4 without reading data. Native timeout/FIFO-empty conditions stopped just before the original 1 µs delay call; delay/ROM execution was not replaced with a stub.

The upper diagnostic function checks whether transfer result is 0. On success, it combines response byte 1 as the high eight bits and byte 2 as the low eight bits, then writes the value to a log or optional output pointer. The actual current initialization caller passes that output pointer as **null**. No path comparing the response against a specific constant to pass was found. There is therefore no need to insert an arbitrary device ID as though it were a real identifier.

This is the consumption contract for that call. It does not establish actual device identity, physical response, or allowed values for other commands. A follow-up model can select an explicit diagnostic-response fixture and distinguish it from actual stock identity. The fact that the value is not used for initialization authentication does not make an unknown wire response physical verification.

## Connecting DMA and the original pixel callback

After reset commands in original initialization, a clear function calls the registered rectangle callback and then the DMA submission function. Saved actual globals, original BL instructions, and a template establish the connection.

- The CPU pixel callback's buffer pointer and DMA source are both `20094400`.
- The CPU callback uses a 640×480 area, 320-byte stride, and two pixels per byte.
- Even x uses the high nibble, odd x the low nibble. Increasing y advances one 320-byte row.
- Right/bottom are inclusive coordinates. Inputs 640/480 clamp to 639/479.
- The CPU callback pixel area is 153,600 bytes. The DMA template requests 153,602 bytes.

In a declarative fixture filled with `aa` in and around the initial buffer, executing original full clear zeroes only the first 153,600 bytes and **leaves the following two bytes as aa**. A header hypothesis shifting the start two bytes later does not match this CPU buffer layout. The wire meaning of the extra tail and external-device handling remain unknown.

This is a firmware-internal pixel-plane structure. It does not establish actual optical panel resolution, orientation, brightness, or correspondence with the 576×288 logical HUD of Sandevistan/SDK.

## Preview drawn by original ARM

Executed each original's actual registered callback using a separate Unicorn M7 caller. Drawing code was not reimplemented and firmware instructions were not modified. The input scene is our 16-level bands and checkerboard; Python decodes packed memory written by original ARM into PNG.

Checks cover even/odd boundaries, row stride, and clamp for black clear, plus nonzero packed colors aligned to byte pairs. Do not generalize that all partial-nibble boundaries for nonzero colors work. Compared full SRAM with expected results and checked memory outside the buffer, guards on both sides, and tail preservation. No SRAM memory-write hook was used.

Displaying PNG values 0–15 as grayscale 0–255 is a preview convention, not measured physical brightness. Pattern binaries and PNGs from all three images match byte for byte. Opened the stock 2.4 PNG directly and checked bands, checkerboard, and dimensions. Original main tasks did not generate this test scene, and it is not represented as the integrated Renode M55 display viewer.

## Verification and reproduction

One analysis by `tools/inspect_mspi0_rx_identity.py` contains 309 original ARM scenarios: for each of three originals, nine RX, 32 diagnostic decode, four transfer-status branch, and 58 pixel-call cases. Declarative data, timeout, function arguments, and saved native RX frames are recorded separately.

Compare the report/inspector and six pattern BIN/PNG files—eight artifacts total—from final `mspi0-rx-identity-source-02` and frozen `mspi0-rx-identity-frozen-01` byte for byte. Python 101 checks, nine unchanged models, and private assets are recorded in `simulator/mspi0-rx-identity-verification-01/manifest.json`. Preview and source SRAM are preserved outside Git.

The initial literal search failed to find a direct buffer constant and that result was preserved. Actual provenance was established through a global pointer, registered callback, and DMA template. Do not determine frame offset from a separate static address guess alone.

## Next work

Connect an explicit virtual four-byte RX response, FIFO lifetime, completion, and IRQ restoration to MSPI0, then check how far original main goes after diagnostics. Do not extend this to success for generic identity or other unknown opcodes. Then connect this verified pixel plane and actual Renode DMA capture to the viewer and investigate meaningful original-main drawing and the 576×288 logical HUD conversion path.

Overall scope v2 remained 13/29 = 44.8%. The overall goal of web installation, Faceclaw CFW, recovery boot, integrated simulator, and display was in progress. There was no physical access, flash, OTA, persistent write, commit, or external publication.
