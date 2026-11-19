# Simulator Screen Publishing Preview

2026-11-18 · bw-0589. Astra directly inspected the user-approved monochrome dark workbench concept `exec-94d23d46-9bd4-4173-8375-3d45ba00b3a6.png` and implemented it in `web/prototypes/board-explorer.html`, `workbench.css`, and `workbench.js`. No GitHub publication or actual glasses connection occurred.

Board references were the two user-supplied temple photos, an existing video contact sheet, and FCC internal-photo PDF pages 2–5. Additional renders of FCC pages 4 and 5 are retained in a private research folder. Evidence for markings and chip positions follows the [board research](../research/g2-chip-location-and-3d-preview.md). The page's board is an **illustration** extracted from the approved generated concept; it must not be treated as an actual photograph or accurate chip layout. User photos and FCC original photos were not included on the page.

The screen uses a 576×288 virtual stock 2.3 frame from existing `guest-dashboard-preview.png`. App buttons, timeline, and logs are local preview UI, not live Renode logs or firmware execution. There is no physical communication or flash.

Astra compared the reference with WebKit desktop at 1671×941, captured mobile at 390×844, and fixed controls clipped on small screens. Final images are outside Git at `research/workbench-bw589/{desktop,mobile}.png`. In a dedicated Safari task window, 14 checks covered opening/closing four tabs and five board items, timeline 04:59 → 05:00, automatic stop, and log display; the window was closed. The parent also inspected both images and confirmed tunnel JS HTTP 200. The generated concept's system menu and Dock were excluded from web-app content.

The user-requested temporary Cloudflare tunnel served only `web/prototypes/` and remained running for concept review at that time. Final rights/sensitive-information review for public distribution of images/page is separate; the generated PCB illustration is not accurate photo-based modeling.

## 3D board integration (bw-0591)

The existing right-side illustration was replaced with a photo-compared [assembled 3D board model](../../web/prototypes/board-model-bw590/README.md). Default is an approximate model including cover, screws, and flex; `Bare PCB` selects the model without attachments. `Front`/`Back` camera requests and selection logs are provided. The board uses rotatable DOM `model-viewer` and depends on an external CDN. The panel labels it an estimated model, not a photograph or measurement.

In a dedicated Safari task window, model loaded state, cameraOrbit request after Back, and new-model loaded/UI log after Bare PCB were checked; the window was closed. A 90-degree Z-axis display was configured to align the board alongside the screen. Actual rendering of this orientation and mobile layout were not newly captured visually. Temporary-tunnel HTML and JS syntax were checked. The static guest screen and preview timeline remained unchanged and were not connected to actual Renode execution/communication.

## Default board front correction (bw-0592)

The default view, where the board appeared edge-on, was corrected. Vertical rotation was moved to the first axis to match model-viewer orientation order. Actual Chrome 1200×800 rendering confirmed the default front and back shown by the Back button. WebKit could not be verified because its executable was not installed. No physical device was operated.

## Orientation, icons, and protocol examples (2026-11-18)

The board front was rotated 90 degrees clockwise from the previous screen and menu symbols replaced with linear SVG icons. The screen is named Emulator. Initial logs included a HELO example and HOLD explanation based on upstream g2-bootloader-patch [UART2 wire protocol v2](https://github.com/drdaeman/g2-bootloader-patch/blob/6198d70e18293caebf8314d2e40bd3b1d0a5ee16/PROTOCOL.md). Challenge 0 and relative time were illustrative synthetic values and checksum was 0x48. This was an example of the patched bootloader, not a stock-bootloader capture, live emulator output, or actual device communication. No HMAC value was shown. Chrome confirmed model loading, back switching, playback-icon change, and logs.

At the user's request, illustrative explanatory wording was hidden and time display changed to ns format. Initial packets and times remained synthetic examples; browser time conversion was not evidence of nanosecond-precision measurement or emulator time.

## Recorded virtual-time display (2026-11-18)

Initial packet examples were replaced with BLACKWALL_BOOT_WIRE responses from the actual saved `original-boot-cli-native-bw548-02/renode.log`. Relative to reset, virtual UART0 response `01 80 0d 00 01 00 00 01 73 0a 07 80` at 20,129,100 µs, `01 80 10 00 01 00 00 03 9f 02 c1 81` at 20,229,100 µs, and the stop when the first complete screen was observed at 20,739,792 µs are shown. These packets are virtual UART0 responses in main, not bootloader UART2 HELO. Recorded times come from a virtual model executing original firmware; they do not represent physical glasses time or cycle accuracy. Exact individual timing of observed boot → main handoff was absent from the log and was not invented. UI interaction logs use browser elapsed time.
