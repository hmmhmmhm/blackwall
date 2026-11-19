# Recovery preparation and execution boundaries

Current status: **offline tools prepared; actual device recovery unverified**. This document is neither execution approval nor a guarantee of recovery from every failure.

Follow-up bw244 [recovery ownership research](recovery-owner-flow.md) confirmed compiled UART2 worker authentication, RAM upload, CRC, and entry to API3 invocation without executing main. Writer and full boot/case integration remain incomplete. Upstream recover()'s pending OTA warning is not a stop gate; do not automatically invoke the raw CLI before enforcing the pending/unknown stop criteria below in an actual execution wrapper.

## Preserved material

Base folder: `~/Library/Application Support/Blackwall/recovery/private-boot-candidate-01/`. Pinned upstream source, original 2.3.2.14, stock 2.4.0.24, Faceclaw/38 bundle, private boot candidate and exactly matching recovery.key, and build receipts are retained. `source/build/` contains case.bin, dump.bin, checksum.bin, recover.bin, and manifest. `recovery-tools-manifest.json` records each RAM tool's length/SHA256. Case relay is 5,508 bytes and MRAM writer 264 bytes. All were host-built and not executed on a device.

`host-venv/` is a persistent execution environment separate from temporary research venvs. crc 8.0.0 and pyserial 3.5 wheels are retained in `wheels/` and installed offline from those files. `wheel-hashes.json` is preserved. It is not fully independent of Python itself or OS/USB drivers. Keys and firmware remain outside Git. This folder is not an original device dump.

## Checks currently available

### Version-specific recovery sets

The 2.3 candidate is kept in `private-boot-candidate-01/`, the 2.4 research candidate in `private-boot-24-candidate-01/`. `tools/check_recovery_set.py` selects a profile by **full local patched-boot SHA256** and matches hashes of patch, recover, dump, checksum, case files, and private key. `docs/data/recovery-artifact-profiles.json` permits only two currently verified builds; new builds are not automatically registered.

This checker imports no communication module and invokes no upstream executable. It has no `--write` option. Example output must be a new file.

```sh
python3 tools/check_recovery_set.py \
  "$HOME/Library/Application Support/Blackwall/recovery/private-boot-24-candidate-01" \
  --output /tmp/blackwall-recovery-set-check.json
```

Both `recover.bin` files are 264 bytes, but internal MRAM function addresses are `0x42e83d` for 2.3 and `0x42e84d` for 2.4. Do not choose by main version or file size. Upstream `load_program` checks only each file against its accompanying manifest and does not locally catch moving payload and manifest together from another build. Subsequent upstream device preflight checking boot prefix and this offline set check are separate stages.

Five `tests/test_recovery_set.py` tests with actual private fixtures passed. They checked two correct sets, wrong writer/key in both directions, missing/corrupt required files, and misuse of main-version strings. Results remain in each private folder's `recovery-set-verification.json`. This checker is neither a security boundary intercepting upstream CLI execution nor a wrapper approving/executing actual recovery commands.

Even with `local_artifact_pairing_valid=true`, `installable=false` and `hardware_validated=false`. Local candidate hashes do not prove which boot is installed on a physical temple; case 1.2.57 fixture does not prove the owned case version.

### Existing image checks

Project `tools/audit_assets.py` checks input SHA, components, and ranges. Preserved folder's `host-venv/bin/python validate-local.py` prohibits serial open and passes two bundles to upstream recover.py without --write. Both images passed local checks with zero device-access attempts. This does not run main app or iPhone app.

## Prerequisites for considering actual recovery

1. Confirm target side's actual boot/hash, hardware and main, and actual case version.
2. Confirm exact compatibility of that boot candidate and case RAM relay code.
3. Confirm exact key/image pairing and availability of recovery host/USB path.
4. Obtain and verify current MRAM original backup and original contents of additional boot pages.
5. Check pending OTA state; do not automatically continue if unknown or pending.
6. Present specific side, image SHA, write range, verification, and interruption response to the user and obtain approval for that operation.

Case RAM-relay execution and boot hold are not treated as simple reads. Hash match of a case firmware distribution file does not establish the owned case's actual version.

## Paths and limitations by failure state

| State | Path to consider | Current evidence |
| --- | --- | --- |
| Normal main and BLE | Single-component OTA | Web software mock verification; unverified on user's hardware |
| Dead main, healthy patched boot and compatible case | Case USB → UART2 → RAM tool → MRAM main recovery | Upstream source support; actual full-main physical recovery unverified upstream too |
| Damaged boot, key mismatch, or incompatible case | Reassess availability of a software recovery path first | No current recovery guarantee; hardware access/service may be necessary |
| Installation/recovery fails on one side | Stop work on other side and record/verify failed side | No dual-temple atomicity |
| Transfer ACK timeout/disconnect | Leave outcome unknown and consider readback/new plan | No automatic block retransmission |

Upstream MRAM recovery backs up original, writes body, writes application vector last, and reads back. It is not atomic rollback against power loss. An upstream CLI suggestion to rerun is not approval for subsequent writes and is not automatically executed by Blackwall. Preserve failure logs, backup, target, and hashes and replan.

## Meaning of returning to stock

Restoring stock main alone can leave patched boot, codec, and other components unchanged. Stock 2.4 and Faceclaw base codec payloads differ, so a main-only restoration is not judged full official-app functionality or full stock.

Full stock requires matching actual device's original boot and all modified persistent areas. Writing only a distributed stock boot prefix may leave appended code/pages. Do not fill pages with unknown original contents using arbitrary erase/padding and call it restored. Boot restoration is a separate high-risk operation removing the existing recovery path. Full-stock procedure is currently unverified; installation readiness is not complete before these prerequisites are resolved.

## Follow-up: external Apollo PMIC watchdog

In bw139's [original PMIC path](../hardware/power/pmic-charger-storage.md), both stock and CFW requested PMIC watchdog reset-mode configuration. Current model stops before that write; actual start, expiry, and inherited boot state are unknown. Existing Apollo internal watchdog tests did not verify this device. Separately confirm how PMIC target/kick/disable/reset is maintained in recovery boot wait, RAM payload, and dead-main paths. Do not extend this into a guarantee of physical recovery.

Bw140 follow-up: recovery patch already has PMIC feed implementation and compiled-MMIO mock tests. Three originals' intended/live RAM profiles matched its expected values. Follow [detailed contract](../hardware/power/pmic-watchdog-recovery-contract.md); the earlier unknown external watchdog means actual timer, bus, scheduler, and device-recovery integration remain to be verified, not that implementation is absent. Current main simulator does not support recovery CONT/read6 flow.

## Follow-up verification of virtual watchdog model

Bw-0141 [virtual PMIC watchdog](../hardware/power/pmic-virtual-watchdog.md) checks split transfer, virtual time, kick, STOP, and reset requests in an explicit initial stopped state. Three original main inputs were observed only through configuration/commit, with Start=0. Do not use this as compiled recovery-feed integration pass or physical recovery evidence. Read6 status/reserved bytes are 0 only in tests selecting a separate mock.

Follow-up bw-0142 [pinned recovery-feed ARM integration](recovery-pmic-feed-integration.md) verified actual function IOM CONT→split read4+2→kick under explicit mock conditions. Mismatch, existing power, and pin states return without a kick and preserve PRIMASK 1. Guest off request is distinct from off completion after host query. This does not substitute for full recovery boot/manager/long reception, physical watchdog, or device restoration verification.

## Scope of 2026-11-17 virtual full-stock verification

[Original-main-based boot restoration](main-driven-boot-restore-results.md) matched synthetic virtual-original 4 MiB and boot/main/all modified-area hashes, plus fresh stock boot/main/frame. This is offline verification of a pinned stock 2.4 profile. Virtual boot tail 0 is not a device-original backup and ROM internals are a functional model. Earlier resident recovery writer self-overwrite failure, original pending ROM, factory INFO1/same-board authentication, RTC error-log boundary, and physical prerequisites remain. This result alone does not execute raw CLI or physical restoration/installation.
