# Development Direction Prioritizing Safe Installation and Restoration

> 2026-11-13 bw342: Active scope is emulator-only scope v3. For current status and reproduction, prioritize the [capability catalog](../architecture/emulator-capability-catalog.md); for the next sequence, use the [emulator roadmap](../architecture/emulator-roadmap.md). The material below records an earlier phase; do not treat its historical progress, priorities, or initial CPU table as current state.

Recorded 2026-11-10. This was the direction reflecting the user's three answers. It superseded the iPhone-first milestones in `m0-architecture-proposal.md`. Specific implementation, tool adoption, and hardware writes had not yet been approved.

## Objective at the time

Additional objective explicitly requested by the user: build a **hardware simulator for CFW development based on stock firmware**. Pursue it alongside the existing web installation/recovery preparation objective, without reducing it to a replacement goal. The [simulator proposal](../firmware/firmware-simulator-proposal.md) records comparison of actual stock and CFW code behavior in the same scenarios and incremental peripheral-model expansion. The additional objective was approved; detailed design was proposed. Passing simulation differs from physical recovery validation or installation approval.

Subsequent user approval authorized the proposed development sequence. Under the active goal including display output, the [first runner](../architecture/simulator-runner-status.md) was implemented and the first unimplemented access reproduced for three stock/CFW inputs. The earlier statement that the design was proposed predates this approval. Full board and display remained incomplete.

The first value was safe, easy custom firmware installation and return to official firmware. Instead of first making a separate native companion, reuse official-app communication and data as far as possible. After small experiments verify text, shapes, animation, sensors, and app-data display, develop Sandevistan's design into a smooth Blackwall UI.

The user specified **web flasher + g2-bootloader-patch for recovery + Faceclaw/g2flash-based code**. Do not interpret official-app reuse and CFW development as mutually exclusive. Local builds and mock verification without installation, and remaining integration issues, are documented in the [offline compatibility check](offline-compatibility-check.md). This was not a combination ready to install.

Preparation for installation-package implementation proceeded under the then-active goal. A [web installer design](../archive/web-installer-design.md), [2.4 boot support investigation](../bootloader/bootloader-2-4-analysis.md), and [Faceclaw 2.4 rebase scope](../archive/faceclaw-2-4-rebase-scope.md) were added. After the author's [2.4 → Faceclaw support explanation](https://github.com/jimrandomh/faceclaw/issues/56) was confirmed, reuse of current Faceclaw was prioritized for investigation. A complete 2.4 port was removed as a mandatory prerequisite. The mixed recovery-boot combination and actual downgrade were neither approved nor verified. A local file inspector was built; the web writer and installation-readiness objective remained incomplete.

## Proposed stages

| Stage | Outcome | Actions not yet permitted |
| --- | --- | --- |
| M0 Installation/restoration preparation | Actual device inventory, exact original/restoration images, web installer source review, single-temple procedure and interruption scenarios | Scanning, pairing, flashing, running case analysis tools or RAM payloads |
| M1 Limited installation and stock restoration validation | Physical evidence after specific approvals for each image, one-side target, validation, and restoration | Simultaneous installation on both sides, automatic case updates, unattended retries, arbitrary security changes |
| M2 Small display/sensor experiments | Establish limits of text/image/IMU/location/status and data integration available through the official app/Even Hub | Assuming features absent from the SDK automatically become active through CFW alone |
| M3 Minimal CFW extensions | Demonstrate compatibility of specific missing display, local animation, and transport capabilities with preserving recovery | Unverified rebase, early boot changes, arbitrary address changes |
| M4 Sandevistan UI port | Preserve high contrast, information hierarchy, and consistent navigation; add smooth transitions based on measurements | Automatic expansion into a full OS or all existing features |

M1 requires, at minimum, understanding the limitations of paths remaining when main or boot fails. The existing boot patch had not physically validated full-main recovery. Stage numbers do not remove that risk or authorize work. Mock and source experiments for M2 that are possible on stock can proceed independently.

## Reusing the official app

The [official architecture](https://hub.evenrealities.com/docs/get-started/architecture) is **Even Hub web code → official-app WebView/SDK bridge → official-app BLE → G2**. Initially the phone WebView would handle logic and data processing, while stock G2 handles display and input. This can begin without an independent native app.

[Official Device APIs](https://hub.evenrealities.com/docs/build/device-apis) include device state, IMU, phone location, and input events. At registry inspection the SDK was 0.0.16, but do not generalize existing Sandevistan 0.0.11 performance results to a new SDK/app/firmware combination. Some APIs depend on app version and permissions. Do not interpret IMU pace codes as Hz.

The SDK is not an interface exposing all data held by the official app or arbitrary BLE transmission. Do not assume access to every other app's notifications, private DB, translation/conversation history, or music information. Integrate external services through paths with appropriate APIs and permissions. Do not invent `callEvenApp` names to bypass API limits.

Official documentation states that animation APIs and direct Bluetooth are not exposed. Distinguish experiments creating motion through repeated phone-side image/text updates from animations on the firmware's own timeline. Smoothness, power, and BLE costs of the former can be measured first; do not promise high FPS.

Faceclaw's `evenhub-extensions/README.md` states that `getFaceclawExtensions()` is null in the official app. **Installing CFW alone does not add a Faceclaw host API to the official app.** Whether a verified official-app message path can invoke a custom renderer, or a separate minimal transport is needed, remains unknown. Revisit the need for a companion only after investigating this.

## Next focus of the discussion at the time

First define read procedures to identify both sides' main, boot, and hardware, as well as case and official-app versions. Do not equate the existing app information display with the actual boot image. Begin web-tool review with static source and file validation; first classify whether buttons labeled connect or inspect also cause reset, RAM execution, or case-mode changes.

The user's photo confirmed the official app's combined glasses firmware display **2.4.0.24** and model **S211**, and the user confirmed the installed official app was also **2.4.0**. The case version is not shown in the app. App build number, actual case version, and individual main, boot, and hardware versions for both sides are unknown. Follow the [device inventory](../archive/device-inventory.md); do not treat unknowns as installation compatibility.

Later bw274: [first HCI command contract](../hardware/communication/em9305-first-write-command.md). The planned first transmitted packet is `fd01`, an eight-byte read at address `00f04b88`. The actual response is unknown and affects the trim-update branch. Existing RAM/source and an ARM fragment were analyzed without native restart or physical-device access.
