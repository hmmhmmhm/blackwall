# MSPI1 Page Program and the Original KVDB Path

## Results and scope

Task `bw-0193`. Implemented page program on NOR backing in emulator RAM. Pinned ARM main from stock 2.4, stock 2.3, and Faceclaw ran unchanged from main reset. Guest branches, return values, and delays were not forcibly skipped. Existing synthetic identity, memory, power, and logical SDR assumptions remain. This did not reproduce full ROM/bootloader boot.

Each original completed 178 programs and 112 sector erases, passed the valid-KVDB-header branch 57 times, and stopped on a read at the `NVdb` start address `0x1ff8000`. Access was blocked because it was outside the declared KVDB range `0x1fc0000..0x1ff8000`. This is evidence of program/readback and the valid-header branch, not normal return from the upper DB initialization function or successful full boot.

| Input | Program completed/started | Bytes written | TX words | Next PC |
| --- | --- | ---: | ---: | --- |
| Stock 2.4 | 178/178 | 2337 | 613 | `0x4e8a46` |
| Stock 2.3 | 178/178 | 2333 | 612 | `0x4db672` |
| Faceclaw | 178/178 | 2333 | 612 | `0x4db672` |

Each observed 704 controller-off/XIP restorations. The common next request is instruction `0x6c`, CTRL `0x100461`, address `0x1ff8000`. Matching stock 2.3 and Faceclaw counters and first 16 header bytes does not prove all stored data is identical or migration-compatible. Do not conclude the four-byte stock 2.4 difference is a schema difference either.

## Model contract

- Supports PP `0x02`, 1..256 bytes, a 16-word TX FIFO, and capacity backpressure. The original supplies TX after starting CTRL, so all data is not required in advance. Final-word padding is not written.
- Addresses within a page wrap at a 256-byte boundary. All target bytes must be within the allowed range. Stored values are existing value AND input; erase is required to change 0 back to 1.
- Program is explicit opt-in. Default duration 0, read-only backing, absent WEL, protected status, unset EN4B, and unsupported configurations/ranges are rejected.
- Wire completion and device completion are separate. The wire waits if TX is insufficient. WIP/WEL remain set during device program and clear with the content change on completion. It progresses separately from controller off, and device completion does not generate a new controller IRQ.
- Full scenario Reset atomically cancels incomplete wire/device work and preserves already completed backing contents. This is not a physical power-loss or partial-program model.

Unit 100 µs and original-run 1,000 µs are explicit mock times, not evidence of measured latency, power, or NOR endurance. First-16-byte `prefix_words` are host diagnostic reads. Guest execution evidence is the separately observed `KV-header-valid` branch with R0=1.

## Tests and evidence

There were 271 unit/regression conditions, including FIFO full/backpressure, 256-byte streaming, page wrap/padding, bit AND, WEL/WIP, disabled/read-only/protected, stuck, clock abort, device Reset, retry after partial-TX Reset, completion after controller off, and absence of asynchronous IRQ. Passed 25 source-contract checks, six original native conditions, and 154 evidence-audit checks.

Evidence outside Git under `simulator/`:

- `mspi1-program-contract-01/report.json`: manufacturer PDF, HAL FIFO, and original CTRL → TX call order.
- `mspi1-program-main-02/`: three normal originals and stock 2.4 default/read-only/stuck.
- `mspi1-program-verification-01/report.json`: initial 154 checks.
- `mspi1-program-verification-02/report.json`: 154 checks re-comparing current model, original bytes, existing native logs/reports, and asset hashes when work resumed. Native execution was not repeated.

Default and read-only blocked at the prior PP boundary with zero writes/TX. Stuck retained one start, zero completions, and FF contents. After returning timeout twice, the original tried to read the next sector `0x1fc1000` while busy; this was blocked. Safe fallback was not established.

The first `mspi1-program-main-01/stock24` overflowed 4,186 of 8,282 observation events and was not adopted as complete observation evidence. After reducing only host observations and rerunning, each of the three normal cases had 2,147 events and zero drops. Repeated points `status-byte`, `status-result`, `CQFLAGS-saved`, `MSPI-power-off-return`, `XIP-retention-restored`, and `MSPI-retention-state-restored` were excluded while corresponding counters were retained. Prefix comparison uses the same label-removal and sequence-renumbering projection. Do not extend this to a full instruction trace or records of each excluded event.

The existing read-only review by an agent inheriting the parent model suggested partial-TX Reset/retry and negative completion-IRQ tests, which were incorporated. Astra was not run.

## Next boundary and recovery implications

Next investigate NVdb consumers and initial-content requirements in original code. Do not arbitrarily extend FF backing to NVdb merely because the blank KVDB scenario progressed.

The subsequent [NVdb consumer investigation](nvdb-consumer-contract.md) statically identified factory DB initialization and an erase call path when magic fails. Backing had not yet been expanded or that path executed at that point.

Running the app itself can change external NOR settings and databases. Restoring main, bootloader, and MRAM does not prove KVDB/NVdb preservation or version migration. Preservation/restoration of original external NOR and corresponding boot-patch support remain separately unverified.

All content changes occurred only in local emulator RAM. Original firmware files and glasses were unchanged; there was no scan, connection, RAM payload, OTA, or flash. Full boot, integrated display, and physical installation/recovery remained incomplete; product criteria stayed 13/29, 44.8%.
