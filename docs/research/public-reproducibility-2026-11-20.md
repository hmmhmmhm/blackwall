# Public reproducibility corrections

## Priority and status

| Priority | Finding | Result |
| --- | --- | --- |
| Critical | Public stock run depended on an undistributed hardware model and initial memory files | The four frozen model components are included with their original SHA-256 values and notices. The stock profile generates the two missing uniform `0xa5` memory fills and verifies their hashes. |
| Critical | The pinned Renode image was not available to external users | Published the same Linux ARM64 image in GitHub Container Registry, pinned by manifest digest. An unauthenticated download of the manifest, configuration, and all six layers was checked against their digests. |
| High | Documentation implied Faceclaw was available through the stock boot report | Added a separate pinned Faceclaw 38 main-reset-to-frame command. It does not execute the bootloader, and arbitrary custom images remain unsupported. |
| High | Project instructions forced Korean on other users | Agent guidance now follows the user's preferred language. |
| Medium | Restricted terminal encodings could not print the scenario list | Replaced non-ASCII command output and added an ASCII terminal regression test. |
| Medium | Missing container could leave a partially initialized volume | Setup now checks for the pinned image before creating a volume and reports the public pull command. |

## Verification

- Stock 2.4: an independent shallow clone of the public repository used only the matching boot and main images, the published model, generated memory fills, and the pinned image. The `normal` run produced an HTML report and its execution audit passed. This run was performed on macOS ARM64 with Docker; it does not establish Windows or Linux host compatibility.
- Faceclaw 38: a separate public shallow clone ran the pinned main image from its main reset vector and produced a 576×288 guest frame and HTML report. GPU rejection count, CPU fault flags, and declared guard accesses were zero. This is not a bootloader-to-main or physical-device test.
- Registry: an unauthenticated client downloaded and hashed the container manifest, configuration, and every layer. The configuration image ID is `sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649`.
- Test coverage includes stock profile and volume checks, Faceclaw image/vector and result rejection, and ASCII-only CLI output. No physical device was connected.

The public commands do not yet support arbitrary firmware, other Faceclaw versions, or a verified stock-bootloader-to-Faceclaw handoff. Firmware and private device backups are not published.
