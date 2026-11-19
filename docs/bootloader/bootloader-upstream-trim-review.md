# Upstream updates and trim-dependent recovery entry review

2026-11-17 · bw-0557/0558/0559. Current upstream and original power-initialization inputs were compared without removing protections from the existing candidate. No physical device, installation, or CFW feature development was performed.

## Actual current upstream clone/build/test

`drdaeman/g2-bootloader-patch` HEAD is `42e27e9c999a340e8b7af406b83a52dc56fcf926`. Compared with previous research baseline 6198d70, it adds storage deferral and full-image allowlist preflight. `src/bootloader.c` and `src/platform.h` are byte-identical between commits, so callback protections remain.

The [new initialization order](https://github.com/drdaeman/g2-bootloader-patch/blob/42e27e9c999a340e8b7af406b83a52dc56fcf926/PROTOCOL.md) initializes NOR/FS after UART probe. Source-supported installation targets remain boot 2.3.2.14 and case 1.2.57. Distinguish developer hardware-tested labels from Blackwall virtual verification.

A git archive from the full clone was extracted into a separate private build directory. Without source changes, existing legitimately held stock bundle SHA/CRC were checked and build used the public default authentication key. Results:

- Current release: `7010d103d02a49333362ec185fb04c9657626f97cec5240063375d1c52e55a7e`, 159744 bytes, exactly matching upstream allowlist.
- Previous release: `06f8a8d59f6351461aa9ce45cbc2a6697172cdca872ec77552325301ae175cc4`, reconstructed using the upstream storage-deferral test's restoration procedure; also matches upstream allowlist.
- 125 upstream tests passed, failure/error/skip 0, serial/BLE open attempts 0. Only macOS host crypto tests used Apple clang/system runtime. Upstream test files/firmware code were unchanged.
- Main extracted and CRC-checked from the same official 2.3.2.14 bundle was 3922604 bytes, SHA `69f9ef63997c9bb53e5b97f83cc330e93651577ab1595ac57dcb481c3e513b9c`, SP 2007fb00/reset 61902b. It was not mixed with legacy main 2.3.0.24.

This does not mean the default key is secret. The default in [upstream auth.py](https://github.com/drdaeman/g2-bootloader-patch/blob/42e27e9c999a340e8b7af406b83a52dc56fcf926/tools/g2patch/auth.py) is public. This work verifies authentication-code behavior, not a claim that the default key provides per-user access control.

## Callbacks depend on input revision/trim

Public pinned HAL SPOT manager constructs function tables by chip revision, trim, and patch tracker. Among the first five source function pointers, +0x0c/+0x10 correspond to PCM2.0 tempco postpone/pending handling. Upstream platform names the same slots power pre/post callbacks. Complete SDK ABI equivalence to the binary is not claimed, but original functions' flag setting/pending handling and native values support the correspondence.

Pinned virtual CHIPREV 23 and synthetic trim 0 correspond to the PCM2.0 branch. At native manager point:

| Boot combination | Two callback words | Actual result |
| --- | --- | --- |
| Existing 2.4 research port + stock 2.4 | 42d91b / 42d925 | Guarded fallback→main, worker 0 |
| Current 2.3 release + same-bundle main | 42d90b / 42d915 | Guarded fallback→main, worker 0/UART2 TX 0 |
| Previous 2.3 release + same-bundle main | 42d90b / 42d915 | Guarded fallback→main, worker 0/UART2 TX 0 |

Upstream storage deferral addresses another important failure path, but **did not remove the unmet callback-guard condition under current synthetic trim 0**. Do not generalize this to recovery failing on every G2 hardware instance.

## Original initialization boundary for trim 1/2

`info1TrimRevision` is optional readonly virtual input. Default -1 retains existing zero/erased fixture. Explicit 0/1/2 changes only INFO1 TRIM_REV word 42003310. Host does not change callbacks, code, checks, or RAM globals. Default metadata, ADC fixture, and other words remain. Shared INFO1 owner and MRAM source relationship are also checked.

Thirty-three pure C# conditions verified profile values, neighboring metadata preservation, read count/reset, and rejection of writes, invalid profiles, and incorrect owners. Earlier 31 conditions predate shared-owner strengthening and remain with RED.

Current 2.3 release ran trim 1 and 2 separately from actual reset. Both strictly stopped at **PC 48, 42003370/read4**, where original initialization reads additional factory information. Boot/main bytes unchanged, guest fault 0, policy violations 0; manager/worker/main not entered. This value is absent from the current sparse fixture. Earlier revision research across three originals also had this unsupported address, but these are new full-reset runs of exact 2.3.2.14 boot/main/current release.

Classification of other trims is source-supported; **worker creation and authentication success are unverified**. Additional NVM was not arbitrarily filled with 0 to proceed. Actual glasses revision/trim and factory shadow remain unconfirmed. New virtual profiles are not promoted to physical device compatibility.

## Preflight and remaining work

Current [recovery preflight](https://github.com/drdaeman/g2-bootloader-patch/blob/42e27e9c999a340e8b7af406b83a52dc56fcf926/tools/g2patch/recovery.py) checks all 159744 bytes and `KNOWN_BOOTLOADER_SHAS`. Do not assume current upstream tool accepts existing custom-key 2.3 research image and 2.4 port as-is. Local artifact pairing checks and current upstream hardware-tested allowlist are separate. The allowlist was not modified to bypass it.

BV05/06 remain incomplete. What is needed is concrete provenance and power-initialization contracts for supported revision/trim/INFO1 inputs, not a modification deleting callbacks. Full integrated restoration under BV10/11 is also unproved. Independent original vector branching and virtual MRAM forbidden-write verification continue. Overall completion is not increased based on test count.

Evidence: private `simulator/callback-ownership-audit-bw557-01/report.json` (36 checks), `upstream/g2-bootloader-patch-review-bw557-01` clone, `recovery/upstream-stock23-bw558-01/{manifest,tests-report,rebuild-command,cleanup}.json`, native `upstream23-{current,previous}-native-bw558-01`, `upstream23-current-trim{1,2}-native-bw559-01`, `info1-trim-{red,green}-bw559-*`.

Owned build ELF/objects, duplicate bundle, test venv, and more totaling 90,984,069 bytes were immediately cleaned up. Source archive/LICENSE, pinned release/payload bin/json, same-bundle main input, source/asset hashes, build/test logs, reproduction commands, and native analysis remain. Original material and other tasks' assets were untouched. Clone is clean; no external posting, glasses operation, or subagent execution occurred.
