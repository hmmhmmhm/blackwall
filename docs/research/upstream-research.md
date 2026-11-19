# Upstream Source Research — 2026-11-10

Status: Initial static investigation. Only source and official CDN files were read. Upstream build, installation, and flash scripts, Bluetooth, USB/UART, and RAM payloads were not executed. This document records proposals and evidence; it is not compatibility certification.

## Commits and licenses

| Repository | Default-branch HEAD inspected | License |
| --- | --- | --- |
| [Sandevistan](https://github.com/hmmhmmhm/sandevistan) | `7d68cb9a9d3668a7e24bc4b730a3daa505d0ab3f` | MIT |
| [Faceclaw](https://github.com/jimrandomh/faceclaw) | `70ec2a0d6afd92e8185234e57ab013fcb596bf4d` | GPL-3.0, README says GPLv3 |
| [g2flash](https://github.com/jimrandomh/g2flash) | `845f665e0dfdcfd06b7d3a294388de6f17a5bd59` | GPL-3.0 |
| [g2-bootloader-patch](https://github.com/drdaeman/g2-bootloader-patch) | `6198d70e18293caebf8314d2e40bd3b1d0a5ee16` | MIT; separately check BearSSL notices |
| [openCFW Research](https://github.com/kalanihelekunihi/evenRealities-openCFW-Research) | `524b9b0814395c517065e11edeb844a36155ae19` | No root LICENSE found; individual third-party licenses do not authorize use of the whole repository |

Pin these commits when reviewing linked code again. Copying, translating, or linking GPL code requires separate license review; a private repository does not eliminate obligations. Initially use them as references. Proprietary Even firmware is not covered by these licenses.

## Evidence classification

- **Local file verification:** Downloaded file SHA-256, JSON comparisons, and container structure checked in this session.
- **Source-supported:** Code implements behavior or checks a limit. This does not mean execution or physical-device success.
- **Developer physical-device report:** Upstream author or owner's device-test record, not reproduced on Blackwall hardware.
- **Developer claim:** Documented support or compatibility claim, distinct from per-device validation.
- **Hypothesis / unknown:** Design inference or insufficient evidence; not used for safety judgments.

## Sandevistan

Compared the [README](https://github.com/hmmhmmhm/sandevistan/blob/7d68cb9a9d3668a7e24bc4b730a3daa505d0ab3f/README.md), `src/g2-canvas.ts`, `fast-canvas-transport.ts`, `fast-canvas-types.ts`, and `canvas-hud.ts`.

React/TypeScript runs in the phone WebView. The HUD divides a 576×288 Canvas into four 288×144 PNGs and passes them through the Even app SDK bridge. Four SDK calls do not mean four BLE packets. Full transfer order is ID 3 → 5 → 2 → 4; right-page refresh is 3 → 5, map 2 → 4, and upper right 3. Successful tile bytes are cached and skipped when unchanged. One refresh owns transmission; busy input/updates are dropped instead of queued. Only tile calls within that refresh overlap to a limited extent.

Interaction uses scroll to change pages, tap for detail/selection, and double tap to return or hide/restore. The semantic model, separation of state/render/transport, high-contrast hierarchy, and policy of updating only necessary regions are worth preserving. React components and DOM Canvas code cannot be ported directly to SwiftUI or firmware. A smaller approach is to extract and redesign data/input semantics independent of SDK bridge types.

Developer physical-device report in the [palette comparison](https://github.com/hmmhmmhm/sandevistan/blob/7d68cb9a9d3668a7e24bc4b730a3daa505d0ab3f/docs/hardware/2026-07-31-g2-hud-palette-compression.md):

| Metric | Original PNG | Four-level palette |
| --- | --- | --- |
| Total PNG size | 50,031 bytes | Median 22,821 bytes |
| Encoding | Median 22.5 ms, n=4 | Median 96 ms, n=8 |
| Encoding + SDK transmission completion | Median 2,468 ms, n=4 | Median 1,855 ms, n=8 |

These are not measurements from this session, optical display completion, pure BLE transfer time, or sustained FPS. The record indicates that reduced data volume shortened overall time despite increased palette CPU cost. Raw traces were not recalculated in this investigation. The July 30 pipeline record has empty timing fields and is a partial pass. Do not extend the README's broad hardware-validated label to all combinations. These values do not automatically apply after Even app/firmware changes.

## Faceclaw

The main app uses a phone-side NativeScript/TypeScript UI and Kotlin Multiplatform `FaceclawKit`. In addition to the Android-oriented README, an actual iOS implementation exists. `native/kotlin/shared/src/iosMain/.../IosBleCentral.kt` implements CoreBluetooth connection, discovery, notification, and write flow control; `IosGlassesSession.kt` connects to the shared session core. `app/bootstrap.ios.ts` starts NativeScript screens according to onboarding state. `iOS/Faceclaw/ContentView.swift` is a Hello World template and must not be mistaken for the main app's SwiftUI implementation.

`package.json` maps `build:ios` to `scripts/ios.sh build ios --for-device` and `run:ios` to `scripts/ios.sh run ios`. A prepare hook builds the Kotlin framework. NativeScript/Node, Kotlin/JDK/Gradle, Xcode, and signing setup are required. The README's `notes/ios-development.md` was absent from the inspected commit. The build was not run, so actual installability is unverified.

`DeviceInfoProbeFlow.kt` performs authentication → prelude → settings queries on stock as well. `IosStockFlows.kt` contains the iOS host. This separate path does not perform OTA or display, but a new connection can trigger SMP bonding. Thus it is intended for reading, not guaranteed stateless or free of persistent writes. A normal session uses `setRequiredFirmwareRevision(38)` to restrict other firmware. Do not start the whole session for stock investigation.

Based on `firmware-compat.ts` and `settings_ext.c`, the current contract is **Faceclaw/38**, reported in settings protobuf field 100. App version 1.0.0 and firmware revision 38 are separate. The app permits `>=38`, while the g2flash README recommends the exact recognized string. For Blackwall, an explicit allowlist of verified revisions/capabilities is preferred. Absence of field 100 is a common stock form, not proof of an unmodified bootloader.

The phone owns rendering and app state, while CFW performs some composition and animation using a 640×480 framebuffer, resource cache, display list, and time expressions. Input distinguishes ring/temple sources. Volatile lease code returns to stock when authority expires, but this is not proof of safety against boot failure or all malformed inputs.

Installation/removal uses OTA after preparing CDN stock files with local patches or unchanged. The recommendation was to exclude this builder/flasher/onboarding from M0.

## g2flash

Reviewed `build_cfw.sh`, `patches/cfw_patches.json`, `apply_patches.py`, `patch_compress.py`, `stock_abi_230.json`, `settings_ext.c`, `display_list.c`, `image_buffers.c`, and `g2flash.py`.

The current canonical base is **G2 2.3.0.24**, not a general patch for arbitrary newer firmware. JSON verifies the file using original SHA-256, expected old bytes, and final SHA-256. Generation depends on clang Thumb code and exact stock function/RAM addresses. The main app loads into MRAM `0x00438000`; the 32-byte OTA preamble is separate. The flasher checks destination, length, CRC32C, and conservative end address `0x007F8000`. The description that the bootloader does not check the boundary is an upstream analysis claim; device behavior was not reverified here.

Local comparison confirmed that Faceclaw's committed patches and g2flash JSON have **all 39 operations and input/output hashes identical**. Current code /38 takes precedence over older Faceclaw/17 README references. Patch locations are 36 in main, one append, and two container metadata locations; bootloader payload is unchanged. However, the output bundle **still includes the original stock bootloader**.

After authentication, OTA sends six EVENOTA components sequentially using FILE_CHECK, 4 KiB blocks, and END/CRC checks. It does not immediately replay a block with ambiguous ACK; after reconnecting, it restarts the whole component. Temples are also sequential, but the default target is both. `--stop-before flash` may already reach BEGIN and FILE_CHECK, so it is not a manual read-only inspection. No flasher was run in this investigation.

Removal of CFW through official-app OTA is an upstream test claim. Upstream also states that compatibility with all official-app functions and EvenHub is unverified. If an update bundle includes a bootloader, preservation of the recovery patch cannot be assumed.

## g2-bootloader-patch

Reviewed [README](https://github.com/drdaeman/g2-bootloader-patch/blob/6198d70e18293caebf8314d2e40bd3b1d0a5ee16/README.md), [PROTOCOL.md](https://github.com/drdaeman/g2-bootloader-patch/blob/6198d70e18293caebf8314d2e40bd3b1d0a5ee16/PROTOCOL.md), `src/bootloader.c`, `watchdog.h`, `ram_api.h`, echo/dump/checksum/recover examples, flash/patch/recover/altboot tools, and recovery/link/firmware helpers.

The target is stock bootloader **2.3.2.14** and case **1.2.57**. PROTOCOL records main **2.4.0.24**, hardware **5**, wire **2**, and RAM API **3**. Host and loader use the same source revision. The fixed bootloader SHA is checked in input files and recovery preflight, but the flash tool does not automatically verify every actual version and hardware condition.

It replaces three stock calls and appends code. During an approximately 500 ms UART2 boot window it supports HOLD, RAM upload/RUN, and CONTINUE. The case executes a USB/UART relay payload in RAM and is designed not to change case flash. The code path operates without the main app, but requires normal ROM/SBL, the patched bootloader, case, contacts, and power.

RAM code is 2–512 bytes of Thumb PIC, privileged and unisolated, and RUN cannot be interrupted. Even dump can fault on an invalid address. Although the protocol has no direct flash command, the recover payload writes MRAM, so do not automatically treat RAM execution as safe. The default HMAC key is public, the challenge is nonrandom and permits replay concerns, and subsequent messages lack MACs.

After body validation, recover commits the leading 16-byte vector and preserves a backup and CRC of the target range. It is not atomic. It restores only main and does not restore external NOR resources. Physical reports cover right-temple stream/CRC rejection and writing, reading back, and restoring 1 KiB of unused MRAM. **Full main replacement is untested on physical hardware.** Left-side selection is implemented, but equivalent physical evidence was not found.

## openCFW Research

No top-level README or LICENSE was found; `docs/` contains only `.gitkeep`. `tooling/*-status.manifest.json` primarily uses **2.0.7.16 / 2026-03**, distinguishing identified/inferred/unknowns. The product manifest has build_status=skeleton. Use it to understand Apollo510B main/boot separation, external NOR/LittleFS, and left/right role/provisioning; do not directly apply its addresses or recovery assurances to current 2.3/2.4. Case MCU model and NV layout remain among the unknowns.

## Local check of official distribution files

Two files were downloaded from the CDN and confirmed to match upstream pinned SHA values. Patch generation was not run.

Additional local checks found each bundle's six payload SHA-256 values and TOC/subheader CRC32C matched, and 38 guards with old bytes among the 39 patches matched the stock file. The remaining operation is an append. This is offline file inspection, not patch-output reproduction or a device installation check.

| Bundle | SHA-256 |
| --- | --- |
| [2.3.0.24](https://cdn.evenreal.co/firmware/1dbdf37b03a1169c384945e94d671371.bin) | `187ccf2bcc5c17a212106e8a376745511e8289c4232b634a7ea94b9bf25a0979` |
| [2.3.2.14](https://cdn.evenreal.co/firmware/7892790e40cffbae6db8a635b335e17f.bin) | `26b6067665a441b779c47f6b95427b8b4bb5f502aaf527466dadce628aeb00b2` |

The 2.3.0.24 bootloader payload is 149,755 bytes / SHA `52ed1c4d043f278f9011d2f2e6555b668ef2ff1e312695f5c28fa7986523b75b`. The 2.3.2.14 payload is 149,760 bytes / SHA `22a2b98e606b4d296e957a3a8b600a2158497638d79485c817c2025536329ba7`, matching the patch requirement. Both bundles' case raw data excluding the 32-byte preamble have SHA `773b6d4cfdaf0a5a74a557e3babe8222a0ae813436b76a7437c1096d2c60d677`, matching the patch's case requirement. This is **distribution-file agreement**, not confirmation of the user's case version.

Conclusion: Do not adopt a workflow that installs the current complete Faceclaw bundle unchanged after the recovery patch. Retaining only CFW main or rebasing remain design candidates; do not implement or apply them before validating component, boot ABI, resource, and OTA combinations.

## Additional reference: G1 decompilation

At the user's suggestion, [JohnRThomas/even_realities_decomp](https://github.com/JohnRThomas/even_realities_decomp) was pinned to commit `f571782aedb6fdefbcbfe2a4d1e309bb47143581` and 38 relevant files inspected. Since it concerns G1/nRF5340, do not apply it to G2 peripherals, addresses, or OTA. Eight panel opcodes overlap with pinned G2 g2flash code; use them as search leads for packed 4bpp, display tasks, and BLE behavior. Differences in ID response length, Linux helper pointer-size transfer length, a build not linking the entire decompilation, and unknown root license preclude adopting the code unchanged. [Detailed review and application boundaries](even-realities-decomp-review.md).

## Additional reference: G2 BLE protocol

[i-soxi/even-g2-protocol](https://github.com/i-soxi/even-g2-protocol) was pinned to commit `b227335f5fbecb7d4ede3748c36e098ef88850fa`. UUIDs, services, teleprompter ordering, and CRC are useful for reuse of G2 stock features and mock packet analysis. The 34-check offline audit reproduced schema compilation errors, sync field differences, and length failures for long ASCII/Korean pages. Capture wire interpretation, authentication, and compatibility with our 2.4 device remain unverified; upstream BLE examples were not executed. [Detailed review and usage boundaries](even-g2-protocol-review.md).
