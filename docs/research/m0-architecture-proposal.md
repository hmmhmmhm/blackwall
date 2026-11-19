# M0 Architecture and Roadmap — Discussion Draft

Current status: The user's subsequent decision on 2026-11-10 **superseded the iPhone-first priority**. This file records the original proposal. For the direction at that time, see the [safety-first roadmap](safety-first-roadmap.md) and the root `ALIGNS.md`. A native app is not an initial required deliverable.

Recorded: 2026-11-10. This architecture was not approved by the user, and implementation was not started. It builds on the [research](upstream-research.md), [risk assessment](../bootloader/recovery-risk-assessment.md), and [compatibility matrix](../firmware/firmware-compatibility-matrix.md).

## Smallest starting point

The recommendation was an **independent native SwiftUI app, a minimal CoreBluetooth adapter, and a mock**. M0 would test startup, state transitions, and logs without glasses; M1 would add only reviewed stock information probes. M0 provides no reason to install CFW or a patched bootloader.

An alternative is to base the work on the entire Faceclaw iOS app. It offers connection and rendering assets, but also brings a NativeScript/Kotlin build, a CFW contract, installation UI, and a much larger app scope. A third option, integrating a native app, CFW, and recovery from the start, is deferred because of version conflicts and verification gaps. The minimal native app has the disadvantage that its BLE wire implementation and error handling need fresh validation.

```text
Single SwiftUI diagnostic screen
  ↕ User connect/disconnect intent, state, and logs
Connection state + per-device observations (small Swift models)
  ↕
Mock or CoreBluetooth transport
  ↕ M1 only: reviewed stock G2 queries and responses
Stock G2 L/R (actual versions currently unknown)
```

This diagram separates conceptual responsibilities; it does not propose a package or framework for each role. The screen shows connection state, selected device, observations, and bounded logs. The mock also reproduces disconnects, denied permissions, timeouts, and malformed responses. App startup and navigation must not automatically scan, connect, install, or send display commands.

The recommendation was to keep recovery research in separate Mac host tools and documentation, rather than combine it with a recovery UI dependent on the iPhone app or normal main-firmware operation. M2 would verify the exact tool, case, and loader combinations and limitations.

M0 excludes OTA service writers, firmware downloaders or builders, arbitrary raw-packet transmission UI, and bootloader commands. Information requests permitted in M1 must check external input length, frame CRC, response type, and side, and terminate pending requests on timeout or disconnect. Logs have bounded size and do not export credentials, secrets, or device identifiers by default. Background reconnection and always-on operation are not yet required.

## Firmware state presentation

Display a recognized field 100 string as, for example, `Faceclaw/38 observed`. Display absence as `Known extension not observed`, no response as `Unable to determine`, and a different string as `Unrecognized extension`. Do not turn these results into a claim of fully verified stock firmware. Bootloader, case, and hardware are separate fields; leave them unknown if they cannot be read. A new Blackwall protocol should consider major/minor versions, explicit capabilities, and limits, but need not be designed or implemented in M0. For unrecognized states, the recommendation is to avoid custom commands and restrict operation to diagnostics.

## Concepts to retain from Sandevistan

Consider the meaning of its data models, glanceable information hierarchy, consistent tap/scroll/back navigation, updating only necessary regions, caching after successful confirmation, and avoiding an unbounded backlog. Four tiles, 576×288, and four concurrent calls are strategies for the existing SDK environment, not an established Blackwall transport contract. Discuss both the benefit of dropping updates while busy and the possibility that the latest state may temporarily lag. Migrating all existing features, such as maps, news, and AI, is out of scope.

## Rendering alternatives

The power and latency assessments below are design inferences, not measurements on a new device.

| Approach | BLE and latency | Memory and power | Complexity and recovery risk | Current evidence |
| --- | --- | --- | --- | --- |
| Full iPhone bitmap transfer | Large payload and encoding/transfer cost | Phone pixel buffer and codec; frequent BLE use | No firmware modification needed if the stock display contract is verified | Sandevistan uses the stock Even app SDK path; equivalence of native direct display is unverified |
| Partial updates | Sending changed regions can save bandwidth; multiple tiles risk partial display | Requires a cache of the last successful state | Stock/native protocol limits need verification | Sandevistan implements successful-tile caching and region updates |
| Firmware primitives / display list | Repeated frames need not be resent | Glasses need CPU time, resource cache, and validation | CFW parser, address ABI, and worker intervention increase risk | g2flash /38 implements primitives, text, and list/time expressions |
| Firmware framebuffer composition | Depends on transport; local redraw is possible | Code uses a 640×480 packed 4bpp buffer, 153,600 bytes each; additional buffers and caches cost more | Memory pressure and stock display ownership need verification | `image_buffers.c`, `display_list.c`; not evidence of GPU use |
| Hybrid | Text/primitives plus images as needed, optimized by purpose | Cache and font synchronization on both sides | Both paths and failure fallback need verification | Candidate for later; not decided now |
| Apollo510B GPU | Potential savings are hypothetical | Driver, DMA, and power domains unknown | High for the initial scope | No GPU access evidence in the reviewed CFW path; implementation has not started |

Initially the phone would own state, data, and user actions, while the glasses retain stock connection and information responses. Potential reasons for firmware changes include resolution, input, local animation, or transmission latency targets that a verified stock path cannot meet. First establish the actual requirements and stock limitations. Do not promise power or performance improvements without measurements.

## Proposed milestones and completion criteria

| Stage | Scope | Completion evidence and boundaries |
| --- | --- | --- |
| M0 | Xcode native iPhone app, mock state and logs, CoreBluetooth foundation | In addition to simulator build/launch, **confirm signing, installation, and launch on a physical iPhone**. Only Xcode 27.2 installation was confirmed; implementation was not performed |
| M1 | Manual BLE discovery → selected connection → reviewed stock information queries and disconnect | Record results by version and side, pairing side effects, timeouts, reconnection, and permission failures. No unattended automatic connection initially. Discuss a display greeting separately later |
| M2 | Establish recovery readiness | Document inventory for both sides, case, image hashes, independent host procedure, OTA conflicts, interruption response, full-stock limitations, and validation plan. Do not mark readiness complete without installation and physical recovery validation |
| M3 | Investigate Blackwall firmware compatibility | /38 patch reuse, main-only and rebase alternatives, boot preservation, stock OTA/app compatibility, capability allowlist, and static/mock validation. Defer patching if it is unnecessary |
| M4+ | Features to determine with the user | Undecided. Select only features justified by measurements |

The numbering does not grant flash permission or specify every dependency. M2/M3 source research can proceed independently of M1. Actual boot installation, RAM experiments, and MRAM recovery each require their own prerequisites and specific approval.

## Questions for discussion

1. Should Blackwall's first value be **a personal HUD more responsive than Sandevistan**, or **a developer tool for observing G2 state and protocols**? Both are possible, but one initial user experience is needed.
2. Initially, should the user **normally use the official Even app and connect Blackwall only when needed**, or eventually make **Blackwall the primary companion**? BLE connection ownership and iOS background requirements differ. Choosing the latter does not automatically add background functionality to M0.
3. For the first screen experiment, should the priority be **preserving the existing Sandevistan layout**, or **using small text and basic shapes to check latency limits**? Decide after a native display command is verified; do not send it to the glasses now.
