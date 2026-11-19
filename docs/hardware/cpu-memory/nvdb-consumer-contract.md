# NVdb Consumer and Initialization Boundary

Task `bw-0195`. Investigated the `0x1ff8000` read following [page program](mspi1-page-program.md). Peripheral models and backing ranges were unchanged and native execution was not repeated. Analyzed three pinned ARM mains and the existing stack at the stop point.

## Structure confirmed in original code

All three originals define the `NVdb` partition at `0x1ff8000` with length `0x8000`. The existing native stack contains this partition table pointer, address, and length 16. This observation supports attribution of the read, but no NVdb header or data was actually read.

| Input | Factory initialization entry | KVDB initialization call target |
| --- | --- | --- |
| Stock 2.4 | `0x55f034` | `0x58602e` |
| Stock 2.3 | `0x52bf20` | `0x562d96` |
| Faceclaw 38 | `0x52bf20` | `0x562d96` |

The initialization function selects DB index 1 and passes the DB name `factory`, partition name `NVdb`, and default KV descriptor. The descriptor-construction function records count 9 and an SRAM table pointer. **The defaults cannot be read by interpreting the SRAM pointer as a ROM offset.** This distinction was established in the initial investigation; actual default KV contents remain unverified. Key strings `nvMagic`, `nvSysDt`, `nvMAC`, and `nvSCald` are analysis clues, not results of reading a physical MAC, calibration values, or secrets.

Optional controls 2/3 store callbacks at DB+`0x1c`/`0x20`, respectively. Do not interpret them as write protection or read-only settings. They correspond to the lock/unlock structure in public FlashDB-family source, but the exact linked version is unknown.

An initialization result of 0 advances to subsequent processing; the failure path sets R0=8 and returns. After success, the code looks up `nvMagic` and compares it with `0x55550022`. The missing/mismatch path has a separate DB recreation call. Its callee calls a format function in a sector-size loop, and format calls the partition erase wrapper. Therefore this path **cannot be classified as a read-only check**. This write path was confirmed statically; it was not a native execution result on NVdb. Validity of defaults, preservation of individual factory data, and successful recreation remain unverified.

## Verification and limits

The later [blank NVdb scenario](nvdb-blank-scenario.md) used a separate opt-in to observe a successful lower-level DB initialization return and the next 172-byte read boundary. The limits below concerning default contents and physical verification remain.

`tools/inspect_nvdb_consumer.py` uses 63 checks to compare the three pinned main hashes, initializer instructions and literals, DB index/arguments, success/failure branches, magic, callback storage, sector-format → erase calls, partitions, and existing native logs/reports and stack.

Final evidence outside Git is `simulator/nvdb-consumer-contract-04/report.json`. Two instruction-offset errors in the initial checker were fixed by comparison with actual disassembly. The 51 checks in `contract-02` predate addition of the format call chain and are distinct from the final 63 checks. These checks do not execute the entire call path or verify actual NVdb data.

The next safe development experiment is a **blank NVdb scenario distinguished from physical factory data**. Explicitly define KVDB and NVdb boundaries and observe how the guest formats, creates defaults, and retries. Design it as a separate opt-in without silently changing existing `erased-kvdb` semantics. Do not inject known magic or a fake MAC as normal factory values to pass a branch. Do not claim generated settings can replace physical factory calibration.

For recovery, restoring firmware main alone cannot promise restoration of external NOR factory data. Preservation of actual originals, supported restoration operations, and version migration need separate verification. External NOR restoration support in the current boot patch is also unknown.

There was no glasses scan, connection, RAM payload, OTA, flash, or MRAM write. Full boot, integrated display, and physical recovery remained incomplete; product completion stayed 13/29, 44.8%.
