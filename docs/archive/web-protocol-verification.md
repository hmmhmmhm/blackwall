# Web OTA packet verification

2026-11-10. This is an intermediate installation-preparation result, not a completed actual web installer.

`web/ota-packets.mjs` is a pure JavaScript module importable in a browser. It creates transfer frames and parses ACKs without calling Bluetooth APIs. Its reference is `tools/g2patch/ble_ota.py` at g2-bootloader-patch commit `6198d70e18293caebf8314d2e40bd3b1d0a5ee16`.

Fixtures were generated from upstream Python output for `frames(193, bytes(i % 256 for i in range(length)), 255)` at lengths 0, 1, 230, 231, 232, 233, and 4096. These include CRC crossing a fragment boundary and a 4096-byte block. Data is synthetic and contains no proprietary firmware bytes.

Implementation followed confirmation of nine failures in the unimplemented stub. `node --test tests/ota-packets.test.mjs` passed **9 tests**. All frames for the seven inputs matched upstream output byte for byte. Additional checks reject corrupted ACKs, fragment counts/indices, reserved bytes, lengths, invalid input types, and more than 255 fragments.

ACK parsing accepts only single-fragment responses and checks headers more strictly than upstream. Whether this restriction fits every actual OTA response has not been checked on a device. It returns sequence and SID; matching against the expected request belongs to the next session layer.

Remaining work includes operation-specific file verification and confirmation, a single-temple session, no automatic retry on ACK timeout, Web Bluetooth adapter, web UI, mixed-firmware compatibility review, and recovery package. This test proves no BLE transfer, write, boot, or recovery success. No device access occurred.

## Bootloader transfer session

The upstream boot-only flow was ported to `web/boot-ota-session.mjs`: authentication → BEGIN → header → 4096-byte blocks → END → liveness check. There are no retries or automatic subsequent operations; a session can be used only once. Response failure yields outcome-unknown, and even a successful response yields awaiting-verification. The input file is copied before the first asynchronous operation to prevent external tampering from affecting it.

`node --test tests/*.test.mjs`: **14 passed**. Five session tests cover normal order, timeout at each of seven exchange points, rejection of an incorrect component before transfer, concurrent-call rejection, and stopping on NAK at each OTA stage. Only mock transport was used. ACK SID 0xc0 and length 2 are conservative implementation assumptions, unconfirmed on hardware.

This remains a transfer primitive. Actual adapter notification registration, waiting, timeout and stale ACK handling, file CRC and SHA verification, device/side identification, and operation approval UI remain. This module alone must not be used as installation authorization or compatibility validation. Main payload is not page-aligned like boot, so it is not forced into this API. The upstream source contract for that component's main transfer must be checked separately.

## Web Bluetooth transport

`web/gatt-transport.mjs` accepts one already-connected device and resolved characteristics, then uses `startNotifications` and `writeValueWithoutResponse`. It neither opens a chooser nor connects directly. It permits one exchange at a time, registers the response listener before writing, and refuses reuse after timeout, disconnection, or write error. It cleans up listeners and timers afterward. Even if a pending write returns after timeout, it does not send remaining packets. It does not claim to cancel a write already handed to the OS.

Six Node fake-GATT tests were added, bringing the JS total to **20 passed**. There were no actual Bluetooth calls. Mocks cover immediate response, timeout, disconnect, concurrent exchange, CRC corruption, and a pending write returning after timeout.

A key remaining limitation: notifications before a new request starts are ignored, but a delayed ACK from a previous block arriving during a new block may not be distinguishable by opcode alone. Sequence echo has not been established upstream, so no arbitrary matching condition was added. Live installation stays disabled until protocol evidence or a safe restriction is established. Device chooser, GATT service discovery, side identification, compatibility/file checks, approval UI, and main transfer remain.

## Main transfer contract and safety limit correction

Pinned g2flash `845f665e0dfdcfd06b7d3a294388de6f17a5bd59`, `g2flash.py` lines 68–76, 617–626, and 653–714 were directly checked. `flash_component` sends the final block at its remaining length. The final block of the 3,829,864-byte Faceclaw/38 main payload is 104 bytes; that of the 3,700,100-byte stock 2.4 payload is 1,412 bytes. Do not page-align as with boot or append arbitrary padding to the final block. The 32-byte preamble is included in transfer but excluded when calculating the MRAM body write range.

The Blackwall Python checker's incorrect MAIN_END at OTA flag address 0x7FE000 was corrected to upstream's conservative APP_MAX_END=0x7F8000. A regression test accepting a synthetic main up to the limit and rejecting four bytes over failed before the correction and passed afterward. All 12 Python tests passed. Full audits of three actual originals, CFW, recovery boot, and receipt were rerun and passed; values matched the existing audit JSON. Prepared research images were not changed.

Upstream wait_ack checks characteristic and opcode but does not compare envelope sequence. This does not establish a sequence echo guarantee. Blackwall's delayed ACK ambiguity remains unresolved and does not justify live transfer.

## Faceclaw and stock main transfer implementation

The boot-only module was changed to `ComponentOtaSession` in `web/component-ota-session.mjs`, and all callers migrated. Operations are boot, main-cfw, and main-stock. The SHA256 of each validated complete main component (header + payload) is pinned in code. Thus CFW specified for stock restoration or a one-bit change is rejected before the first transport call. Full length, type, filename, main preamble destination/length, and 0x7F8000 limit are also checked. Boot retains page alignment and partition size; its source/hash verification still needs connection to separate package checks.

Main sends its final block short without arbitrary padding. Actual CFW and stock components retained outside Git in recovery/web-components were read; reassembly of all transfer fragments matched each entire original payload. The final blocks matched exactly: CFW 104 bytes and stock 1,412 bytes. Both remain readbackVerified=false even after END and liveness response.

Run:

```sh
BLACKWALL_COMPONENT_DIR="$HOME/Library/Application Support/Blackwall/recovery/web-components" node --test tests/*.test.mjs
```

Result: **22 passed, skip 0**. Without this environment variable, two main integration tests requiring proprietary files are skipped; a skipped run is not reported as full verification. Main tampering and a different operation pin were tested using actual file copies. All transfers went only to fake exchange; there was no device access.

Remaining work includes GATT adapter/session integration tests, exact artifact generation/verification integration, single-temple selection/identification and confirmation UI, delayed ACK limitation, codec mixing review, and recovery package. This does not prove completion of the web installer or hardware compatibility of mixed firmware.

## Session–GATT integration verification

`tests/gatt-session-integration.test.mjs` uses a separate mock receiver that does not call production packet helpers. It runs actual `ComponentOtaSession` → `GattTransport` → fake characteristic → notification → session end to end. The mock checks CRC, fragment order/count, SID, same sequence for marker/data, authentication/BEGIN/header/blocks/END order, and reassembles through the final block.

For each actual CFW and stock component, the received header and complete payload matched the original. A disconnect during the second block of a boot-copy transfer left only the first block complete, with no subsequent writes, END, or retry.

With the same private component path, all **25 JS tests passed, skip 0**. This checks the integration gap in prior separate tests. It is not a device transcript, so mock ACK SID/format assumptions are not promoted to physical evidence. Actual notification sequence rules and delayed ACKs remain unresolved. Web Bluetooth chooser, service discovery, device identification, UI, and recovery package remain separately incomplete.

## Enforcing file pins at the transfer entry

`ComponentOtaSession.transfer` was integrated with the common `inspectArtifact`, in addition to the web inspection screen. Duplicate main SHA constants were removed. Boot must also match the private candidate's complete component SHA and size before an authentication packet can be sent. A tampered-boot regression that previously passed structural checks reached transport and failed before the change; afterward it was rejected with zero calls.

Boot session tests were also changed from synthetic zero images to the actual candidate outside Git. Normal order for 39 blocks and timeout stops at each of 44 exchange points were checked. The existing main wrong-operation test was rejected by the common validator's earlier size check, so its expected error string was updated and no increase in transport calls verified.

```sh
BLACKWALL_COMPONENT_DIR="$HOME/Library/Application Support/Blackwall/recovery/web-components" \
BLACKWALL_BOOT_COMPONENT="$HOME/Library/Application Support/Blackwall/recovery/private-boot-candidate-01/boot-recovery-component.bin" \
node --test tests/*.test.mjs
```

Result: **30 passed, skip 0**. Without the environment variables, tests requiring proprietary images are skipped and must not be reported as equivalent coverage. File pins are separate from device compatibility, actual device readback, and operation approval. The session remains a low-level transfer module and live UI is disabled.

## Single-temple selection and connection module

`web/temple-connection.mjs` accepts an explicit side and exact advertisement name to construct the Web Bluetooth requestDevice exact-name filter. It uses DATA/CTRL services and characteristic UUIDs from upstream g2flash.py. Name format is limited to `Even G2_<number>_<L or R>_<6-digit hex>` or `G2_...`. The user's actual advertisement name is unconfirmed, so examples are not used as actual values.

A selection with a different name is rejected before connect. Already connected devices are not adopted. It checks services, characteristics, and write/notification properties and closes connections it started upon failure. One connection is allowed per JS module instance; this does not prevent concurrent connections from other tabs or the official app. Close is repeatable and a disconnect event also releases ownership.

Five mock tests were added: **35 passed, skip 0** overall. No actual chooser, scan, or connect was executed, and it was not connected to the UI. Name matching is not cryptographic device identity or firmware compatibility verification. Chooser cancellation and connection failure are not retried. There is currently no separate cancellation/time limit for chooser or GATT requests that the browser does not return. Do not call it on a real device before approval UI, device inventory, and operation-specific confirmation are in place.

## ACK constraint correction

Three pinned upstream implementations were compared:

- g2flash `845f665`: g2flash.py `wait_ack` checks notify characteristic and opcode and requires payload length >=2.
- boot patch `6198d70`: ble_ota.py `command`/`install` also read the first two payload bytes without comparing OTA SID/sequence. The SID 0xc0 response in test_tools.py is a synthetic fixture.
- Faceclaw `70ec2a0`: StockLinkSession.kt `onNotification` queues the first 2 bytes from a valid OTA notify characteristic frame, and OtaFlashFlow.kt `waitAck` checks opcode.

The arbitrary Blackwall OTA SID==0xc0 and payload length==2 conditions were removed to match the channel/opcode/length>=2 contract above. The GATT adapter registers a listener only for notifications on the selected channel. Auth SID 0x80 and magic echo checks, frame boundary/CRC/single-fragment checks, and incorrect opcode rejection remain.

Synthetic OTA response tests with trailing bytes and a different SID failed before the correction and passed afterward. This compares upstream acceptance contracts; it does not prove an actual device sends that SID. All **36 passed, skip 0**. Complete distinction of delayed ACKs with the same opcode remains unresolved, and sequence echo is not assumed arbitrarily.

## Installation operation coordination layer

`installation-flow.mjs` connects file inspection, one-side target selection, GATT connection, and single-component transfer. A prepared plan internally retains a file snapshot and immutably binds kind, side, advertisement name, and SHA256. Arbitrary objects and plans modified after copying are rejected.

All artifacts currently have installable=false. executeInstallation checks this before the Bluetooth chooser and cannot be bypassed by a user-supplied true flag. This restriction must not be removed with a checkbox. A compatibility profile reflecting device-specific evidence must be designed first. Exact confirmation string, single consumption, and connection cleanup on transfer termination were written, but the full execution path behind the current false gate was not reached or verified at this layer. Mock success of lower-level session/GATT modules does not replace that verification.

Plan forgery rejection, immutable plans with actual pinned files, pre-chooser blocking of unconfirmed compatibility, and rejection of both-side/other-side selection brought the total to **39 passed, skip 0**. The screen did not yet use this plan layer. UI integration and approval-flow review, device-specific compatibility profiles, and actual recovery evidence remain, so the goal is incomplete.

## 2.4 recovery candidate low-level OTA session

`boot-24` was added as a separate kind to `ComponentOtaSession`. It checks the same boot component structure and page boundaries as the 2.3 candidate, but requires a different complete component SHA from the artifact catalog. Swapping files or tampering with payload is rejected before authentication with zero transport calls.

The actual 2.4 research candidate outside Git was used to mock authentication, BEGIN, header, 39 4096-byte blocks, END, and reauthentication. Timeouts were injected at each of 44 exchange points to confirm no retry or subsequent packet and session termination as `outcome-unknown`. Operation and concurrent-call rejection were also run alongside the existing 2.3 candidate.

A virtual GATT endpoint with a separate wire decoder/encoder also confirmed that received headers and combined payloads for both boot candidates matched their originals byte for byte. Injecting a disconnect after one block produced no END or subsequent writes. This endpoint does not emulate a real device, bootloader, or OTA storage.

```sh
BLACKWALL_COMPONENT_DIR="$HOME/Library/Application Support/Blackwall/recovery/web-components" \
BLACKWALL_BOOT_COMPONENT="$HOME/Library/Application Support/Blackwall/recovery/private-boot-candidate-01/boot-recovery-component.bin" \
BLACKWALL_BOOT24_COMPONENT="$HOME/Library/Application Support/Blackwall/recovery/private-boot-24-candidate-01/boot-2.4-research-component.bin" \
node --test tests/*.test.mjs
```

Overall result: **53 passed, skip 0**. Tests skipped without the above inputs are not reported as equivalent coverage. All catalog entries remain `installable=false`, and `executeInstallation` continues to block before the chooser. Session handling of boot-24 does not verify actual device OTA acceptance, MRAM installation, boot, recovery, or readback. The return value also remains `readbackVerified=false`. No actual browser or device transfer was performed for the 2.4 entry.
