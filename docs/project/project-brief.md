# Blackwall Project Principles — Discussion Draft

Recorded on 2026-11-10, based on the user handoff and initial research. This is not approval for product design, implementation, or hardware work.

Blackwall is an experimental project exploring custom firmware and companion paths for Even Realities G2. Its motto is **Safety First, Reversible Always.** The first goal is safe, easy installation and restoration to stock, with maximum reuse of the official app. A locally built Xcode iPhone app is a later option. Sandevistan's concise HUD and predictable controls inform the project, but a full OS, voice assistant, agent runtime, and application ecosystem are not initial scope. Discussions are in Korean.

## Operating boundaries

- Priority: hardware safety > recoverability > correctness > compatibility > power efficiency > performance > features.
- Firmware flashing, OTA installation, persistent MRAM writes, bootloader replacement, vector overwrites, and security configuration changes require **explicit user approval for the specific target, image, and scope of each operation**. Approval for one operation does not authorize the next. Do not bypass protective confirmations.
- The approved scope at this point is repository research, local documentation, risk assessment, design discussion, and installation and connection of the project align skill as additionally requested by the user. Glasses connection, inspection, and RAM execution have not yet been performed.
- Reduce risk in this order: source analysis → mock environment → iOS verification without glasses → read-only hardware inspection → stock BLE → nonpersistent RAM → reversible application firmware → bootloader. This sequence is not authorization to execute. If a recovery patch must be installed first, its own prerequisites and approval are still required.
- Do not treat writes to both temples as atomic. The initial proposal for future writes is to install on one side, verify boot, recovery access, and stock restoration, then consider the other side. The physical procedure may require both sides to be docked.
- Distinguish source-supported behavior, developer reports on real devices, our own hardware verification, design hypotheses, and unknowns. A matching hash does not prove hardware compatibility, signature authenticity, or recoverability.
- Distinguish restoration of the stock main application from full restoration of all modified persistent components. Do not promise that software alone can recover every failure.
- Tie firmware offsets to the exact original SHA-256. Do not consider unknown versions safe. Minimize new nonvolatile writes.
- Show the final draft and obtain explicit approval before publishing external GitHub posts or documents. This document is currently an unpublished local draft.

## Preservation policy

Although the repository is private, do not commit proprietary firmware, device secrets, or raw device dumps to Git. Keep local recovery assets outside the repository: original images, source URLs, full and component hashes, versions on both sides, hardware revision, case version, tool commits, backup coverage, verification results, and a human-readable recovery manual.

CDN downloads are authentic distribution files for analysis. They are not backups of the user's device or known-good images verified on that device. Later offline checks generated and hash-verified a research patched boot image and Faceclaw/38 images, but did not approve them for installation. Scope and hashes are recorded in [offline compatibility checks](../research/offline-compatibility-check.md).

## First-session deliverables

- [Upstream source research](../research/upstream-research.md)
- [Recovery risk assessment](../bootloader/recovery-risk-assessment.md)
- [Version compatibility matrix](../firmware/firmware-compatibility-matrix.md)
- [M0 architecture and roadmap proposal](../research/m0-architecture-proposal.md)
- [Current safety-first roadmap](../research/safety-first-roadmap.md)
- [Web flasher research](../archive/web-flasher-research.md)
- [Project align installation](align-setup.md)
- [Integration checks without installation](../research/offline-compatibility-check.md)
- [Machine-readable research snapshot](../data/upstream-snapshot.json)

Use `docs/` for initial production and research material. Create `ios/`, `firmware/`, `recovery/`, `tools/`, `tests/`, and documentation subcategories after discussing their need and structure with the user. At the user's request, `.agents/skills/align`, `skills-lock.json`, and the root `AGENTS.md` and `ALIGNS.md` were installed and connected. A README has not yet been written. Use lowercase kebab case for filenames under `docs/`.
