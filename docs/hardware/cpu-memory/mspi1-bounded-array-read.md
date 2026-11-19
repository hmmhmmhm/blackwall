# Bounded NOR Read and Blank KVDB Execution

## Model and data provenance

Following the [KVDB region investigation](nor-kvdb-region-contract.md), native execution declared only a **blank KVDB test state at 01fc0000–01ff7fff**. `BlackwallNorReadWindow`'s `erased-range` returns FF for that range. This is not an actual device dump or normal DB image. It supplies no data for adjacent NVdb (from 01ff8000), other NOR addresses, or the XIP aperture.

A separate `synthetic-ramp` profile is unit-test-only data whose values vary by byte position, used to verify FIFO word order, boundaries, and padding. Both profiles are read-only and modify neither host files nor device memory. Profile/start/length must be explicit; ranges outside 32 MiB, zero lengths, and undefined profiles are rejected. Address addition is checked in 64 bits to prevent uint wraparound.

## Supported frame

The original request is instruction 6c (QREAD4B), four-byte address, eight dummy clocks, serial instruction/address and quad data. It requires CTRL low 16=`0461`, CFG value `00010861` excluding three sampling bits, and CTRL1 PIOMIXED=5. QE=1/WIP=0 and explicit MX/known-status/ideal-SDR conditions are also checked. Because 6c itself is a four-byte opcode, the NOR EN4B latch is not required beforehand.

The model does not handle DEV0DDR low-five-bit EMULATEDDR/QUADDDR/DQS/fine-delay control combinations, so it accepts them only when 0. This does not mean all these bits are identical DDR-enable flags. Actual effects of some depend on silicon revision and have no current physical verification. Existing SEPIO/pin-routing and sampling assumptions remain unknown. Support is logical byte transfer, not electrical signals or calibration.

Following HAL's 16-word FIFO size, only 1–64 bytes are supported at once. Longer streaming transfers are not automatically split or completed. Up to 16 words are delivered by queue; bytes inside a word are little-endian and unused lanes in the final incomplete word are zero padding, not NOR content. Existing short RDID/status/configuration results use the same FIFO while preserving prior padding.

Data enters FIFO only on the existing 10 µs mock completion event. New commands are rejected while FIFO is unread. Abort/full Reset removes pending data; controller-only off preserves external backing and accumulated diagnostic history. Program/erase and XIP backing were not implemented at this point.

The 23 conditions in `inspect_mspi1_array_contract.py` compared pinned SVD/header, HAL FIFO constants, and requests from three originals. Also rendered manufacturer PDF page 20's command table to confirm 6c/QREAD4B. Referenced QREAD QE/dummy conditions on page 49 and explicit four-byte command independence from EN4B on page 58. Original PDF, renders, and verification material were preserved outside Git.

## Actual original main execution

| Condition | Observation | Next unimplemented boundary |
| --- | --- | --- |
| Stock 2.4 / blank KVDB | 16-byte read returned success 0 → header four FF words → invalid-header result 8 | PC `4e8a46`, instruction 20/address `01fc0000`/CTRL `00e1` |
| Stock 2.3 / blank KVDB | Same | PC `4db672`, same sector-erase request |
| Faceclaw 38 / blank KVDB | Same | PC `4db672`, same request |
| Stock 2.4 / backing unselected | Zero array reads | Blocked at existing 6c/CTRL `100461` |
| Stock 2.4 / power stuck-on | Zero array reads | Blocked at existing power enable `8400` |

Header rejection was no longer only a static expectation. Original guest copied the received 16 bytes into its own buffer; read-call return R0=0 and four `FFFFFFFF` buffer words were observed, followed by R0=8 on the original error branch. Original code then prepared initialization and completed a second WREN, making WEL=1/status 42, but sector erase was rejected. Do not assess this as successful erase, DB creation, or normal initialization.

In three successful paths backing was read once/16 bytes and that history survived two controller-off operations. Previous 358 events were preserved; final count was 368 with zero drops. PC remained the same as the prior stage because execution stopped in the same generic PIO function, but the operation changed from read to sector erase. Main bytes matched pinned bundles; guest branches, returns, and delays were not forced. Prior synthetic memory/identity/power conditions and main-reset start scope continue to apply.

## Verification and preserved material

Final artifacts outside Git:

- `simulator/mspi1-array-contract-01`: 23 source/request checks and rendered manufacturer command table.
- `mspi1-array-unit-03` and `erased-unit-03`: 46 conditions each, common prefix `mspi1-array-`. Covered nonuniform data, odd lengths, 16-word FIFO, final byte, NVdb and both boundaries, rejection of overflow and 0/65 bytes, invalid lane/address/opcode/timing control, abort, and Reset.
- `unknown-unit-02`, `stuck-unit-02`, `noqe-unit-02`, `busy-unit-02`: four conditions each, covering default block, incompletion, QE0, and WIP1.
- Including RDID 30, repeated-status 44, and XIP/off 39 regressions, 221 conditions total. Regression folders are `mspi1-array-rdid-regression-02`, `status-regression-02`, and `xip-regression-02` respectively.
- `simulator/mspi1-array-main-02`: five conditions covering three originals, default backing, and power failure; input hashes, logs, and reports preserved.
- `simulator/mspi1-array-verification-01/report.json`: 117 checks comparing original bytes, current model, derived SHA, logs/reports, prefix, receive buffer, actual error branch, erase blocking, and more.

Preserved API-absence `mspi1-array-red-01` and initial `unit-01/02` and `main-01`. The mode negative test `mspi1-array-mode-red-01` reproduced an initial guard accepting QUADDDR bit 1; unsupported low control combinations were then blocked. Final judgment uses unit 03/main 02 after that change.

Following read-only review by an agent inheriting the parent model, WIP1 and timing-control negative tests were added. Astra, other model families, and a full conversation audit were not used.

## Next steps and limits

Later [local sector erase](mspi1-sector-erase.md) implemented device completion and content changes, advancing to a page-program request. The following describes the end of the read stage.

Next establish address mode, sector alignment, WEL/WIP, completion, and content-change contracts for KVDB formatter's command-20 sector erase. Do not return success on read-only backing; verify a storage model where actual content and state change consistently inside the local emulator. Keep the NVdb boundary separate. This is not physical-device erase or flash approval.

Normal DB initialization, full boot, integrated display, and physical installation/recovery remained incomplete. Product criteria stayed 13/29, 44.8%. There was no glasses connection, scan, RAM payload, flash, OTA, or MRAM write.
