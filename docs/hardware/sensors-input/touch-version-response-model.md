# Touch package version and optional response model

Work `bw-0235`. Legitimately acquired bundles, original parser/comparator, and consumption path were compared for the four-byte value in [first IOM5 lookup](../power/iom5-first-transfer-contract.md). No glasses/case access or device writes occurred.

## Legitimate package and version field

After verifying existing pinned stock 2.4, stock 2.3, and Faceclaw38 bundles by full SHA and existing EVENOTA parser, `firmware/touch.bin` was extracted. All three payloads are byte-identical:

| Item | Value |
| --- | --- |
| Length | 34720 bytes |
| SHA-256 | `c14456cd4d432815d79700b251c9a575f75c76a3710f4148c0df6ddba4cb7ba2` |
| Magic | `FWPK` |
| Offset 4 little-endian word | `0x02020900` |
| Original-format notation | `2.2.9.0` |
| Version-query response big-endian bytes | `02 02 09 00` |

The verified CRC is CRC32C of the outer EVENOTA component. It does not establish FWPK internal app CRC, code execution, or physical installed version. Touch payload and header are preserved outside Git in `touch-version-research-01`. Current physical touch version remains unknown.

`tools/inspect_touch_version_contract.py` finds and verifies original magic load → compare → branch and version field load/store in three mains. On success original code outputs offset 4 of the 16-byte header read unchanged. Bad magic takes a failure branch without changing the output sentinel. Tests execute only limited original fragments around file I/O/log calls without forcing internal branches.

| Original point | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| FWPK magic check | `0x5834d2` | `0x57ecbe` |
| Header version copy | `0x58352c` | `0x57ed18` |
| Current/package comparison | `0x583c18` | `0x57f404` |
| Mismatch branch | `0x583c60` | `0x57f44c` |

Original comparison branches were checked for equal, current one lower, one higher, and current 0. It compares equal/different, not newer/older. This does not mean the file actually opened in full main or the entire updater ran. 39 checks passed including package/source checks and 18 original fragment scenarios. Results: `touch-version-contract-01`.

## Update-branch scope

Stock 2.4 `0x583e5c` calls touch version query. A subsequent path checks failure and sets a force flag at `0x583eae`. `0x583f0e` queries package version; `0x583fc8` calls comparison. Force flag and comparison affect later path selection. This is original source analysis, not actual execution of read failure, full updater, or DFU.

Therefore do not pass a query failure as a fake error return or create a mismatch with an arbitrary version. This model is a **virtual device scenario matching package version**. This response alone does not establish that update was skipped in the actual full path, or that touch.bin was placed in a virtual filesystem.

## Optional version-only profile

Existing `BlackwallIomRegisterProbe` `pointer-01-only` behavior remains. Only explicit `package-version-only` returns `02 02 09 00` for a four-byte request after pointer01. The profile rejects other registers, lengths, and data writes. A new pointer write is needed to reread after a response; unobserved auto-increment/current-address reads are not assumed.

Returned bytes are a synthetic response for the version verified from pinned package SHA. **This is not original touch-MCU ARM execution or full CY8C4046FNI emulation.** G2 main continues executing original ARM while this external peer models limited behavior. Touch input, gesture, proximity, DFU, and flash are not implemented.

Before adding the profile, native red saw the constructor reject the unsupported profile. Renode handled the constructor exception and exited 133; log is preserved in `touch-version-red-01`. The log confirms profile rejection as cause; this failure is not counted as a general test pass.

After implementation, 25 native checks included FIFO response word=`0x00090202`, completion IRQ, repointer query, and no-response stops for wrong lengths/rereads. Existing pointer-only 18 checks passed again. Evidence: `touch-version-unit-01`, `touch-version-pointer-regression-01`.

## Actual consumption by original main

`tools/touch-version-candidate.json` changes one peer component and an explicit profile from the previous pinned model. Observer, initial memory, PC, branches, and function returns were unchanged. Actual delay loops were not skipped. Results: `touch-version-main-01`.

| Input | Original version cache address/value | Next stop |
| --- | --- | --- |
| Stock 2.4 | `0x20076fac` / `0x02020900` | `0x58236c`, IOM5 peer-write |
| Stock 2.3 | `0x2007783c` / same | `0x57b014`, same |
| Faceclaw38 | `0x2007783c` / same | `0x57b014`, same |
| Stock 2.4 response off | Existing cache 0, returned bytes 0 | Existing read4 `0x582242` |

Three originals read four bytes once and stored them in cache via original decoder. One write/read completed, peer finish 2. IOM Commands=3 includes the next unsupported write attempt, not three completions. Next actual CMD is length-1 write `0x101`, CPU R1=`08`, checked against existing FIFO source path. Pointer08 meaning, expected read length, and configuration structure were not yet established.

Existing event prefix and all UART0 bytes/eight IRQs were preserved. Off control exactly matched previous CPU, instruction count, observations, and stop. This is equivalence of limited observations, not full SRAM, schedule, or silicon timing equivalence.

Saved-evidence audit `touch-version-verification-01/audit.py` passed 176 checks covering pinned original/model delta, input hashes, logs, unit/regression, consumed cache, next boundary, and control. Source copies and SHAs were preserved to avoid retroactive dependence on the current model builder. Python compile also passed.

Next analyze **remaining touch initialization lookups, configuration, and event contracts** as one flow rather than adding individual successful responses per pointer. Package match is not physical verification; full boot, normal font-bank, integrated screen, web-integrated installation, and physical recovery remain incomplete. Overall product fulfillment is 13/29 (44.8%).
