# Recovery risk assessment — preliminary research

Recorded 2026-11-10. Based on [sources and file hashes](../research/upstream-research.md). This is a preparatory draft for a physical recovery manual, not approval of an execution procedure. No hardware was used in this session.

## Risk assessment

| Operation | Preliminary risk | Evidence checked | Unknowns / conditions to proceed |
| --- | --- | --- | --- |
| First bootloader installation | Very high | Pinned stock SHA, three hooks, partition limit, BLE OTA, optional readback CRC twice | New recovery path does not yet exist if first write fails. Check actual boot/hardware of both sides and case, preserve originals, obtain separate approval |
| Stock main app restoration only | High | RAM writer, range backup, CRC, body→vectors-last | Full-main replacement unverified on hardware. NOR resources, NV, case, touch, etc. outside scope |
| Full stock restoration | Unknown / high impact | Code path exists to send stock boot via OTA | No physical evidence of restoring all modified areas, readback, and boot. Bootloader restoration removes its own recovery path |
| Current Faceclaw full bundle + recovery patch | Cannot apply as-is | CFW bundle contains stock boot different from supported version and flasher sends every component | Prohibited until independently verified main-only configuration or rebase. Do not arbitrarily remove boot component to install |
| Both-temple recovery | High / non-atomic | Side selection, sequential operation code, both-side docking requirement | Physical reports mainly concern right side. Interactions with other side and case and reset isolation when one fails are unverified |
| Future candidate mock iPhone app | Low | Local app alone possible | Signing and physical iPhone launch unconfirmed. Current initial M0 changed to installation/restoration preparation |
| BLE discovery/information query | Limited; varies by action | CoreBluetooth / stock probe code exists | Authentication may save new bonding. Ordinary Faceclaw session has additional display/lease operations. Separate minimal path needed |

Risk is a qualitative assessment of impact and current evidence gaps, not a numerical failure probability.

## Two restoration goals

**Stock app restoration:** boot a verified official main with corresponding external resources working. State explicitly if bootloader remains patched. Matching main bytes alone does not establish normal functionality or full stock.

**Full stock restoration:** every modified persistent region is in a verified original state. Beyond boot-prefix hash, verify scope/evidence for later pages containing appended code, main, changed external resources, other controllers, and settings. Original distributed boot is shorter than patch image, so whether reinstalling the original file clears appended regions is unknown. Do not replace device-specific provisioning, calibration, or bond data with a generic stock bundle.

## Current recovery paths and limitations

1. If main app is healthy and exactly compatible, a path exists to install an official image with stock BLE OTA. Faceclaw uninstall uses this path too. Upstream says its OTA updater was tested; it was not verified on the Blackwall user's device.
2. If main app is dead and a supported patched bootloader is healthy, code exists to attempt MRAM main recovery via USB case → UART2 → RAM writer. Read backup, preflight SHA, and CRC verification exist, but **physical full-main success evidence is insufficient**.
3. If patched bootloader is dead or lost, that path itself is unavailable. Public documentation alone has not established user-accessible ROM rescue. Hardware intervention such as disassembly or SWD/JTAG may be necessary; access and success are not guaranteed.
4. NOR filesystem/resource corruption, security configuration damage, and power/contact/case damage cannot be assumed fixed by MRAM main recovery alone.

An independent recovery path from a normal app is different from a claim that all failures are recoverable. No success rate, complete-recovery guarantee, or dual-temple guarantee is assigned.

## OTA and version conflicts

- **Main-only transfer and no writes after boot are different.** Actual Faceclaw/38 and stock main codec-version comparison fragments took the update path when values differed. Query values and files were fixtures; actual DFU was not executed. Do not promise main-only installation preserves codec before checking NOR codec file, actual codec query value, and caller-entry conditions. [Execution scope and results](../hardware/sensors-input/codec-version-comparison.md#caller-version-comparison-update-path-on-mismatch).
- In 27 conditions connected from function entry, force=1 took the update path without querying; continued query failures and short responses took it after error handling. File open/magic failure returned -1. Mode controls and I/O were doubles; update was not executed. **Do not assume query failure automatically blocks writes.** Upper call conditions and actual write range need further research.
- g2flash 2.3.0.24 CFW boot payload differs from stock 2.3.2.14 boot required by the patch. Even if a source patch does not change boot, a full OTA bundle may overwrite it.
- If official stock OTA includes boot, recovery-patch preservation is not guaranteed. Post-install version/readback is needed. Latest official version was not established by this investigation.
- Matching boot/main version strings is not sufficient. Check bundle components, ABI/function addresses, exact case relay code, external resources, and each side's role/NV together.
- Recovery's pending OTA flag may produce only a warning before proceeding on the default recovery path. CONTINUE may reapply staged update, so Blackwall procedure stops until pending state is understood and resolved. Clearing the flag is itself a separate persistent write requiring approval.
- Communication success ACK is not a substitute for installation verification, optical display, or normal boot evidence. Do not automatically reflash after verification failure.

## Identification table required before future work

Record each temple's app version, boot version and actual image hash, hardware revision, left/right identity, case version and relay compatibility, stock bundle and component SHAs, tool commit/wire/RAM API/artifact hash, and previous OTA pending status. Settings field 100 identifies main extension, not bootloader. All remain unconfirmed on the user's device.

## Proposed one-side-at-a-time work

Future approved installation targets one side only. Distinguish upstream requirement to place the other side in the case from writing only one side. Discuss the second side after confirming first-side normal app boot, case-independent handshake/readback, precisely limited recovery verification, and stock-app restoration. Do not automatically choose right because there are right-side experiment reports.

On interruption or power loss, isolate the target side as incomplete and do not begin installing the other. Preserve image, target side, audit, and last confirmed state. Do not retry before checking whether boot is alive. If boot is damaged, do not guarantee case rescue; classify it separately as hardware intervention. Main app recovery itself is a write, so confirm its new scope rather than relying on blanket approval of the interrupted operation.

## Preserved assets

Outside the repository, `~/Library/Application Support/Blackwall/recovery/research-2026-11-10/` retains two initial CDN originals and file/component SHAs and provenance manifest. Subsequent `offline-check-01/` contains the 2.4 original, generated research boot/CFW, hashes, and mock-test material. No confidential device data is included. A known-good device backup, complete original boot partition, per-side versions, physical checks, and an execution-approved recovery script are **still absent**. Collecting research copies and records does not establish recovery readiness. Follow-up results are in [offline checks](../research/offline-compatibility-check.md).

A future manual must separately address normal restoration by target, dead main, dead boot, one-side failure, communication-only interruption, pending OTA, and resource mismatch, with stop conditions and next approval units for each. This document is a preliminary manual of boundaries, not an executable finished manual.

## bw276 — separate persistent BLE controller state

[Original trim/NVM analysis](../hardware/communication/em9305-version-and-trim-nvm-contract.md) found that trim mismatch/force branches prepare `fd07` information page 2 erase and `fd03` write at `0x00405c80` after entering EM9305 configuration mode. This is source-supported risk compared against manufacturer NVM definitions, not verified physical behavior. Only virtual CPU constructor/fragment tests have run; no command was sent to a controller.

Full-stock restoration therefore cannot be equated with restoring Apollo MRAM main/boot. If the controller information area changes, original preservation, restoration path, lock/authentication, and interruption recovery are separately needed. The entire page 2, not merely a few trim bytes, is erased; do not assume no other customer data exists. Actual page 3 manufacturing data and page 2 customer-area contents have not been obtained. Do not assume current device trim is already 7 and skips updating. Virtual NVM is not connected to physical transport; actual reset/erase/program are not executed without explicit approval for each.

## bw278 — BLE key DB in Apollo MRAM

[Original key DB analysis](../hardware/cpu-memory/mram-keydb-source-contract.md) identified original `_AppDbHealUninitSlots` checking ten slots at stride 256 starting `0x7ff000`. Uniform 0 is skipped, but a uniform nonzero value prepares a zero-repair write. Invalid records are handled separately. No actual key DB or physical write was executed, and current three OTA mains contain no data at that address.

Do not equate main/boot restoration with restoring existing pairing state. Separately review preservation of original DB, record compatibility across firmware, automatic repair writes at CFW startup, and re-pairing effects. Do not assume the entire guard region is the key DB; other adjacent tail state remains unknown. Actual backups are sensitive and must remain private; this analysis authorizes neither backup nor device access.

## bw280 — separate OTA marker after record load

In [read-only record execution](../hardware/cpu-memory/keydb-record-load-transaction.md), three original mains consuming a virtual empty key DB were blocked at the next `0x7fe000` read. The following comparison value is existing pending OTA marker `0x55555555`. Do not extend zero/ff supplied to the key DB to this address. Neither actual nor virtual marker value was supplied at this boundary; retain the actual writer hard gate for pending/unknown.

Additional original ARM fragments showed cache-ready wait timeout reaching error-4 preparation, but the immediately following MRAM wrapper had no local branch checking it. Do not use this limited source result as evidence of safe write interruption on cache timeout. MRAM programming was not executed; silicon-ready behavior and recovery from error/power interruption remain unconfirmed.

## bw281 — 16-byte OTA marker write and readiness

The [original marker contract](../research/ota-marker-state-contract.md) shows startup clear setter skips MRAM programming when existing word equals ffffffff, but otherwise prepares to write requested word + 12 ff bytes as a 16-byte unit. Zero and nonstandard values also skip pending branch while preparing a clear write, so non-pending alone does not establish readiness for actual work. Confirm original adjacent 12 bytes, exact write footprint, and readback.

Marker clear request is in initialization and is not an indicator of full app loop/display success. Confirmed direct caller not checking setter result reinforces the need for readback. Full updater/reset/recovery was not executed and actual marker remains unknown. The web entry currently blocks all catalog entries with installable:false, but this is not described as a marker-freshness/provenance-specific gate. That dedicated gate remains necessary before allowing an actual writer.
