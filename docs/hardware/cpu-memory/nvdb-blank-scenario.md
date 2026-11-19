# Blank NVdb Mock Scenario

Task `bw-0196`. Based on the [NVdb consumer investigation](nvdb-consumer-contract.md), added `--erased-nvdb` to the existing original runner. This option does not provide factory data read from a device. It is an experiment executing the original firmware's handling of blank NVdb.

## Selection and boundaries

Existing `--erased-kvdb` backing remains at `0x1fc0000`, length `0x38000`. Only when the additional option is selected is length extended to `0x40000`, making adjacent NVdb `0x1ff8000..0x2000000` start as FF too. One backing contains two contiguous partitions; the full NOR and other partitions are not generated. The verified erase/program, bit-AND, and WIP/WEL model was unchanged.

NVdb selection requires explicit KVDB, XIP restoration, continuous status, and positive erase/program durations. Five CLI checks each omitted one prerequisite and were rejected with exit 2 before output creation. Default preservation was checked with a separate stock 2.4 native run. Its board was byte-identical to the earlier one, it stopped at the existing NVdb starting read boundary, and had no NVdb observation hook.

The bytes of the three pinned mains and entry at main reset were retained. Guest branches, return values, and delays were not forcibly skipped. Existing synthetic identity/memory/power, logical SDR, and retained NOR power assumptions remain; full ROM/bootloader boot or physical timing is not reproduced. Erase/program 1,000 µs is not a measured value.

## Original execution results

| Input | Program completions | Bytes written | TX words | Erase completions | Controller off/XIP restorations |
| --- | ---: | ---: | ---: | ---: | ---: |
| Stock 2.4 | 242 | 3238 | 859 | 128 | 873 |
| Stock 2.3 | 242 | 3234 | 858 | 128 | 873 |
| Faceclaw 38 | 242 | 3234 | 858 | 128 | 873 |

For each, program/erase starts and completions matched and it was not busy at stop. Counters include previous KVDB writes; they are not NVdb-only counts. Compared with the previous 178 programs/112 erases, this adds 64 programs/16 erases. It is not evidence of physical wear, latency, or schema migration.

For all three originals:

- The KVDB initialization call for DB index 1 returned R0=0. **Successful return of this lower-level DB initialization was confirmed.**
- After `nvMagic` lookup R0 was 4. This is the return value of the function analyzed as the number of bytes read, not verification that actual factory values are valid.
- The recreation call/return on magic mismatch and the full factory initializer return point were not reached.
- The next request was instruction `0x6c`, CTRL `0x00ac0461`, address `0x1ff80a1`, length 172. The destination matches the default KV `nvSysDt` SRAM buffer. It was blocked because it exceeds the existing RX FIFO model's single-transfer 64-byte limit. Distinguish this from blank DB initialization failure.

Word 1 of the first 16 NVdb bytes was observed as `0x30424446`. This was a host diagnostic read after stopping and is distinct from guest initialization return/branch observation. Do not extend it to successful full factory initialization, normal boot, display, or physical device behavior.

## Default descriptor observations

Read SRAM descriptors of 15 words plus 12 words at initializer entry and immediately after the next push, without modifying guest data. The only instruction between observations was a stack push and it did not modify the defaults table. The following keys/lengths were confirmed in all three originals. Actual value bytes were not included in this audit.

| Key | Bytes |
| --- | ---: |
| nvString | 9 |
| nvMagic | 4 |
| nvProdMode | 4 |
| nvSysDt | 172 |
| nvAdvMagic | 4 |
| nvMAC | 10 |
| nvSCald | 92 |
| nvSCaldAG | 68 |
| nvBuzzer | 12 |

Keys are terminated ASCII strings in pinned main; value pointers and lengths were checked against SRAM bounds. Matching descriptor shapes and byte counts do not establish data contents, device-specific factory calibration, or version compatibility. No fake MAC, calibration, or magic was injected by the host.

## Verification and evidence

Outside Git under `simulator/`:

- `nvdb-blank-main-02/{stock24,stock23,cfw}`: normal native runs for three originals. Each had 2,596 events, capacity 4,096, zero drops. Existing compact-storage excluded labels were retained, and prior KVDB prefix preservation was compared using a projection removing added NVdb labels and renumbering sequence. This is not a full instruction trace.
- `nvdb-blank-default-main-01`: stock 2.4 native run with the new option off; retained existing board/stop boundary.
- `nvdb-blank-cli-01/report.json`: five missing-prerequisite rejections.
- `nvdb-blank-verification-02/report.json`: 123 final checks comparing current compiled model, original main, derived asset hashes, native logs/reports, prefix, returns, descriptors, guard, and baseline-run preservation. The initial 117 checks were preserved in the earlier report.

The first `nvdb-blank-main-01/stock24` failed **before CPU execution** because I specified a 27-word snapshot above the observer's 16-word limit. The failure log was preserved, and the snapshot split into 15+12 words without changing the existing limit. Do not treat this as firmware failure.

A read-only review by an agent inheriting the parent model suggested strengthening baseline run log/hash verification, which was incorporated. No Critical/Important functional defects were reported. Astra was not used.

## Next implementation and recovery limits

Later [RX streaming](mspi1-array-rx-stream.md) advanced through consumption of 172 bytes to the next power-request boundary. The following is the implementation plan as of the end of this blank-NVdb stage.

Next establish an RX streaming contract that supplies long array reads while retaining the physical FIFO capacity of 16 words. Do not merely enlarge FIFO beyond 172 bytes or complete CTRL first. Compare original HAL FIFO drain and transfer completion order, and verify data and completion IRQ behavior for insufficient consumption, clock abort, Reset, and range errors. First run mock transfers including 172 bytes, then run the same scenario for all three originals.

This success is limited evidence that defaults can be generated in a blank mock factory DB. Preservation/restoration of actual external NOR originals, device calibration, stock/CFW migration, and full-stock restoration remain unverified. There was no glasses connection, scan, RAM payload, OTA, flash, or MRAM write. Full boot and integrated display also remain incomplete, and product completion stayed 13/29, 44.8%.
