# Browser installation tool research

Recorded 2026-11-10. The user requested research into web Bluetooth installation tools for Blackwall installation and stock restoration. Hardware writes to a specific image, target, and scope are not yet authorized. No web tool was run and no device chooser opened. Only remote HTML/JS and repositories were read.

## Candidates and distinct distributions

| Candidate | Source / status checked | Suitability for Blackwall |
| --- | --- | --- |
| [AM-Guru/evenRealities-webflasher](https://github.com/AM-Guru/evenRealities-webflasher) | Commit `2fcdb888facfe9c56672cbe2a3da741b44033c44`, MIT (`LICENSE.md` checked). README, `g2BleOta.js`, firmware/targets, browser capability, and exclusion tests inspected | Research basis for stock installation and reinstalling a responsive app. **Currently explicitly excludes custom firmware**, so must not be introduced as a current CFW installer |
| [SybilSight WebFlasher](https://webflasher.sybilsight.com/) | Published HTML/JS contains Stock/CFW pairs, custom trust, and experimental pins. Site source and AM-Guru fork are not identical | Candidate for custom installation research. Exact source commit of deployed bundle, reproducible build, match to current Faceclaw/38, and physical stock restoration are unverified |
| [even-g2-thai](https://github.com/rayriffy/even-g2-thai/blob/main/docs/flashing.md) | Separate project documents a specific pinned WebFlasher + custom main/stock pair. Explicitly states current 2.4.0.24, Case-USB-only, one side at a time | Reference for limiting a related tool to specific artifacts. Do not repurpose as evidence of Blackwall or g2flash /38 compatibility or recovery |

AM-Guru's README specifies `https://am-guru.github.io/evenRealities-webflasher/` as its default deployment address. This web fetch could not open that deployment, so deployed assets were not verified against the commit.

## Main differences confirmed in actual code

- AM-Guru README and `tests/fork-exclusions.test.mjs` exclude custom firmware from the catalog and both-side installation paths. Being structurally able to read a local file is different from permitting an actual write. `templeFlashTargets.js` has separate digest pins. Removing these protections to send arbitrary CFW is not adopted.
- `flashG2BleSessionsConcurrently()` starts both sessions at the same start gate and waits with `Promise.allSettled`. The default Bluetooth workflow is **both sides concurrently**. Recording failures separately does not satisfy atomicity or a one-side-at-a-time principle. Current Easy Mode is not used as-is for the Blackwall procedure.
- Bluetooth depends on the running main's BLE OTA and sends the full six-component bundle. Preservation of a patched bootloader must therefore be checked separately.
- Advanced Case-USB has a single-side route selection, but is a **running-temple main reinstall** requiring the running main to respond to version preflight. It is not full Apollo bootloader and NOR/subcontroller restoration. Distinguish it from the bootloader patch's main-dead RAM/MRAM path.
- Case analysis can also include reset and ROM mode transitions. Running the case SRAM bridge is nonpersistent code execution, not a simple passive query. Case update/option-bank activation is a persistent change requiring separate approval. Automatic case update is not bundled into initial investigation.
- Browser capability code actually checks `navigator.bluetooth.requestDevice`, `navigator.serial.requestPort`, `navigator.usb.requestDevice`, and `crypto.subtle.digest`. Mac Chromium is a candidate, but support must be checked per environment; do not assume it works in an iPhone browser.

## Scope of SybilSight deployment observation

The HTML received referenced `/assets/index-CXq5MbRi.js`, whose SHA-256 is `ca7d3a236158331bd5e3b1636fbc0214d4e5a4fe5a6d97730ac91fd7295db417`. Static strings include separate contracts such as legacy `Faceclaw/3` and experimental `SybilSight/230.11`. The `hardwareValidated` value in pin metadata is a self-report by the deployed code, not independent physical validation.

Do not confuse AM-Guru HEAD's official-only policy with this deployment's custom handling. The site can change, so do not install based only on a “verified” label at the live URL. A reproducible pinned version is needed with Blackwall's exact main/stock pair, boot effects, one-side operation, and failure-resumption path confirmed. No such version has currently been selected or installed.

## Separation from the official app

A separate desktop browser owning G2 BLE during installation could conflict with the official app connection. Installation-tool guidance and reuse of the official app during normal use are separate stages. For normal use, first use the [official app bridge](https://hub.evenrealities.com/docs/get-started/architecture). An independent iPhone companion is not necessary for installation.

## Proposed next checks

1. Establish how to identify the user's official app, both mains, boot, hardware, and case. Current device values are unconfirmed.
2. Locally verify stock/custom pairs with provenance and full/component hashes. Do not place CFW under a stock catalog label or misrepresent it as a recognized file.
3. Verify the pinned tool's single-side plan, target components, state after interruption, boot preservation, and stock restoration in source and simulation. Compare current AM-Guru as-is, a specific audited custom-capable version, and a separate existing CLI as practical alternatives. Do not yet implement a fork or new UI.
4. Before proposing hardware work, specify exact image SHA, target side, changed regions, backup/verification, and known recovery limits, then obtain approval for that work alone. Restoration is also a separate write.

Preserve the user's direction to find and use an installation tool, but do not make a safety determination merely because it is browser-based. **Easy installation and main-dead recovery have different completion criteria.**
