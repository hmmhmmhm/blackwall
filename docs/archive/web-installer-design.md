# Web installation package design proposal

Status: a review proposal for implementing the goal. The goal is to prepare web installation of Faceclaw-based CFW and a recovery bootloader. Actual device work is not authorized. Initially retaining 2.4.0.24 was researched, but the [Faceclaw author's explanation of 2.4 downgrade support](https://github.com/jimrandomh/faceclaw/issues/56) was subsequently confirmed. Reuse of current Faceclaw is prioritized for review; a full 2.4 port is not a mandatory prerequisite. A path mixing in recovery boot remains separately unverified. This is not approval to change versions or install.

## Deliverables and completion criteria

1. Faceclaw-based main image, recovery bootloader, corresponding stock main/boot, and component manifest reproducible from pinned upstream commits and original SHAs.
2. Locally running web installation UI showing bootloader installation, CFW main installation, stock main restoration, and full-stock restoration as separate operations, without executing them automatically together.
3. Select only one temple at a time. Changing target or operation invalidates prior confirmation. Reject incorrect side, hash, range, component type, version/profile, and interrupted state with reasons.
4. Byte-level evidence that main installation does not overwrite boot and boot installation does not overwrite main. Specify exact changed regions and regions restored to official originals in the manifest.
5. Implementation using an actual Web Bluetooth adapter and the same state-machine tests with transport mocks. Do not present mock success as physical device success.
6. Without actual device information and readback, retain “device compatibility unconfirmed.” Report software readiness separately from readiness to install on the user's device.
7. Reproducible builds, browser mock/file tampering/interruption tests, and installation/restoration manuals. Keep originals, generated firmware, device backups, and secrets outside Git.

Structure, UI, and fake GATT alone with firmware support incomplete do not complete the goal. Conversely, actual device installation is not added as an automatic action in this goal.

## Recommended small structure

```text
docs/                         research, design, verification, human installation/restoration manuals
web/                          browser screen and verification/OTA state machine
tools/                        pinned source/original verification, packaging, analysis
tests/                        transport mocks and file/operation boundary verification
```

Local file checkers were added to `tools/` and `tests/`. At this point `web/` implemented only packet generation and response interpretation; see [packet verification](web-protocol-verification.md). Actual writer and UI were unimplemented. `ios/` and a full OS/runtime are outside scope. Use a pinned source checkout and reviewed patches rather than copying and modifying all upstream. Preserve license notices and GPL scope.

## Web transfer alternatives

Recommended: build a Web Bluetooth component writer based on g2-bootloader-patch's boot-only OTA procedure, with main-only and stock restoration connected as explicit separate operations. Share verification, confirmation, and state recording while restricting permitted components in code per operation.

Alternative A: fork the entire AM-Guru WebFlasher. This expands initial scope to managing numerous case/ring/automatic recovery features, both-side concurrent defaults, and the official-only policy.

Alternative B: use the web only for inspection and package guidance, and install with the Python CLI. This retains the upstream path fastest but does not meet the final “install on the web” goal, so use it only as an intermediate verification method.

## Installation and recovery boundaries

Boot-only installation using a running main's BLE OTA and UART2/RAM/MRAM recovery using patched boot when main is dead are separate protocols. Do not present the first web writer as completion of the second recovery engine. Prepare an independent recovery host with matching source revision, key, and case artifact.

The basic safety flow is local file verification → device/operation selection → version, side, and prerequisite checks → confirmation of that operation → one-side transfer → readback/boot verification → result recording. Do not automatically start the next stage, other side, or stock restoration. If outcome is uncertain at BEGIN/ACK timeout, record it and do not immediately repeat an uncertain block. Do not treat bootloader-region failure like an ordinary main retransmission retry.

Full-stock restoration is more than rewriting the original boot prefix. Prove the state of additional code/pages, main, and modified external resources, and explain before the operation that removing recovery boot changes later recovery options. Preserve unknown regions or reject the operation; do not initialize them arbitrarily.

## Separate work depending on version selection

- Retain 2.4.0.24: independently verify recovery boot binding and Faceclaw stock ABI against the new original. Do not merely remove existing hash restrictions or add a constant delta to every address.
- Upstream version combination: for ordinary Faceclaw installation, the author says downgrade from 2.4.0.24 is supported. They say a 2.4 update will be offered upon returning to the official app and some app features may not work until then. Do not expand this into evidence for mixed main/boot/resource combinations.

Actual device boot, hardware, and case are unconfirmed for both paths. Record that state in the preparation package; do not insert arbitrary values to make it installable.

Subsequent bw241 connected [virtual web installation, RAM storage, and ARM handoff](../research/virtual-web-install-storage.md). The initial description above of writer/UI as unimplemented reflects that earlier state. Actual installation remains blocked; virtual display and actual installability are distinct.
