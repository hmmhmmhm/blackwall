# NOR KVDB Region and First Array Read

## Confirmed purpose

After passing the [repeated status read](mspi1-continuous-status-read.md), the instruction `6c`/address `01fc0000`/16-byte request is connected to a **FlashDB-family sector header read in the `kvdb` partition**. Do not assume this address supplies display bitmaps or main ARM instructions.

The following entries were confirmed in FAL-format tables in all three originals. Magic is `45503130`; records are 64 bytes with 24-byte name and flash name, offset field at +`34` hex and length at +`38` hex. The flash name is `norflash`.

| Partition | Starting offset | Length | End, exclusive |
| --- | --- | --- | --- |
| kvdb | `01fc0000` | `00038000` | `01ff8000` |
| NVdb | `01ff8000` | `00008000` | `02000000` |

Stock 2.4 tables are at main addresses `6d8cd0`/`6d8d10`. Names, offsets, and lengths match in the other originals, whose table addresses were read separately from each pinned main. The end boundary was compared with total NOR size of 32 MiB. The table describes partition definitions included in the originals; it is not a reading of current physical NOR bytes or particular settings.

## Call path and header handling

The original general flash-read function checks partition length and requested range, adds the partition offset, and calls the device read callback. The FlashDB-family function above it reads 16 bytes, then compares word 1 with sector magic `30424446`. Its code accepts `FFFFFFFF` or 0 in the combined field.

| Original | Sector-header read call | Return address on stack |
| --- | --- | --- |
| Stock 2.4 | `584e80` | `584e85` |
| Stock 2.3 | `561be8` | `561bed` |
| Faceclaw 38 | `561be8` | `561bed` |

`tools/probe_nor_partition_stack.py` increased only the host stack observation after an existing native execution stopped, from 32 to 96 words. It also raised the SRAM limit from 128 to 384 bytes. Original main, other inputs, and execution-result fields were identical across the three executions, and the original 32 words were retained. The extended stack contained the header-read return address and current kvdb table pointer. These addresses support the call path at the stop; they do not mean a read that has not returned succeeded.

In 16 bytes of all FF, word 1 is `FFFFFFFF`, so the magic check fails. That branch sets R0=8 and branches to a common epilogue that returns without changing R0. **This interpretation is static analysis, not native execution of the invalid-header branch.** No array bytes were supplied; complete initialization, formatting, and automatic recovery were also unverified. There is no basis to supply arbitrary all-zero data as a valid header either.

## Comparison with public sources

- [RT-Thread FAL](https://github.com/RT-Thread-packages/fal/blob/aa0211218634a613d3638425a830854bd07a0b76/inc/fal_def.h), commit `aa0211218634a613d3638425a830854bd07a0b76`: compared the partition structure and [read implementation](https://github.com/RT-Thread-packages/fal/blob/aa0211218634a613d3638425a830854bd07a0b76/src/fal_partition.c).
- [FlashDB](https://github.com/armink/FlashDB/blob/360a68d0b1f9f02b0d597a9f08c141e28b332c1e/src/fdb_kvdb.c), commit `360a68d0b1f9f02b0d597a9f08c141e28b332c1e`: compared sector-header magic/combined checks and failure-return structure.

Pinned three files each—relevant source, header, and LICENSE—for six files total outside Git in `simulator/nor-partition-source-01`. Git blobs and SHA-256 were checked; both licenses are Apache-2.0. Correspondence with current public sources explains structure and behavior but does not identify the exact FlashDB/FAL version or build settings linked into G2. The actual 16-byte header and check instructions were separately confirmed in the original.

## Installation bundle and data provenance

The three pinned OTA bundles parse into six components: main, boot, touch, codec, BLE, and case. There is no separate component called `kvdb` or `norflash`. **This does not prove that main or codec contains no default KV data.** Initial defaults, migration data, per-device KV contents, and existing DB state remain unknown. Do not arbitrarily map official bundle components to NOR offsets.

The first test candidate is therefore an explicitly declared **empty kvdb test state**. Do not label it an actual device dump or normal DB image; use it to observe what the original attempts after header rejection. Keep adjacent NVdb separate and do not supply arbitrary values for unknown contents. Verify any model-required erase/program against source and NOR contracts separately from physical device writes.

## Evidence and next work

The later [bounded NOR read](mspi1-bounded-array-read.md) confirmed empty-KVDB header rejection through original execution. The following records the state when the region investigation ended.

Outside Git, `simulator/nor-partition-stack-01` contains hashes, logs, and reports for three read-only native reobservations. `simulator/nor-kvdb-contract-02/report.json` is the final result: 66 checks comparing six pinned source files, bytes of three originals, bundles, call stacks, partition, header checks, and return epilogue. The 60 checks from contract-01 were preserved. Review by an agent inheriting the parent model requested verification through the return epilogue, which was added. Astra, other model families, and a full conversation audit were not used.

Next model the 6c frame's address/lane/turnaround and RX FIFO contract, allowing reads only inside explicitly declared backing ranges. Selecting empty kvdb is also a separate explicit profile. Do not automatically generate unknown NOR addresses, XIP bytes, or actual device contents.

Peripheral models and original execution endpoint were unchanged in this work. Full boot, integrated display, and physical installation/recovery remained incomplete; product criteria stayed 13/29, 44.8%. There was no glasses connection, scan, RAM payload, flash, OTA, or MRAM write.
