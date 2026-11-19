# MSPI Read After NVdb and the LittleFS Boundary

Task bw-0209. Analyzed the next blocked point after [shutdown-model execution](crypto-otp-power-off-model.md). The `0x40061000 ← 0x00100461` operation previously called an “MSPI configuration write” is **the start of a 16-byte PIO transfer via the CTRL register**. It is not a problem to solve by allowing arbitrary configuration-register storage.

## Confirmed execution request

`tools/inspect_post_nvdb_mspi_read.py` compared prior logs/reports and derived-input hashes with pinned main bytes from stock 2.4, 2.3, and Faceclaw 38, confirming 67 items. No new main execution or model change occurred. Results outside Git: `simulator/post-nvdb-mspi-read-contract-02/report.json`.

| Item | Observation and original-code evidence |
| --- | --- |
| CTRL | `0x00100461`: 16-byte RX start sending instruction/address/turnaround |
| INSTR | `0x6c` QREAD4B, same command as existing array read |
| ADDR | `0x01400000` |
| CTRL1 | 5, existing logical 1-1-4 path |
| DEV0CFG / DDR | Matches existing logical SDR support conditions |
| NOR status | QE=1, WIP=0 |
| Existing backing | `0x01fc0000..0x02000000`, synthetic KVdb/NVdb only |

The target address is outside existing backing. `BlackwallMspi1ConfigStorage` sends offset 0 to the PIO adapter, whose `readArray` accepts a request only if backing.TryRead succeeds. Thus it is **rejected because the flash address is undeclared, not because a new opcode is missing**. No new data range was attached automatically.

At the original pause, r1 points to a transaction at stack base+32. Length 16, device address `0x01400000`, instruction `0x6c`, and turnaround match original structure accesses and surrounding registers. HAL blocking transfer also reads FIFO after CTRL start. HAL/header were compared with existing pins at commit `61b293a49db34030c545f99101f7ebf6a3050314`. IAR original ABI was not inferred from the current compiler's enum size.

## LittleFS callback

| Location | Stock 2.4 | Stock 2.3 / Faceclaw 38 |
| --- | --- | --- |
| PIO start store | `0x4e8a46` | `0x4db672` |
| Read callback | `0x4834c0` | `0x480b0c` |
| Candidate static configuration table | `0x6f0214` | `0x70df68` |

Each of three return candidates on the pause stack was compared with its actual call instruction. The path is LittleFS indirect read callback → NOR read wrapper → HAL PIO transfer. The original callback calculates:

`device_address = 0x01400000 + block × 4096 + offset`

The read-failure diagnostic begins `lfs READ fail` and records block, offset, size, address, and status. The callback returns 0 when lower status is 0, otherwise `~4`, or -5. After the upper indirect call, original LittleFS `lfs.c` path and an `err <= 0` assertion appear. Both strings and call instructions were confirmed in all three mains. Error-return code in the callback was not separately reimplemented or substituted.

## Candidate configuration table and unknowns

Later bw-0210's [active configuration/policy verification](littlefs-geometry-mount-policy.md) confirmed actual use of this table and configured block count 3008 through three original executions. Candidate/unknown statements below describe bw-0209 at completion. Actual volume contents and completed mount/format remained unknown.

Searching each main for the exact four-byte representation of the read-callback Thumb pointer yields one aligned reference. A table read from before that reference has context 0, candidate read/prog/erase/sync pointers, and these numbers:

`16, 256, 4096, 3008, 500, 4096, 256`

Candidate program and erase callbacks point to read callback+`0x38` and +`0x70` respectively. Adjacent functions in stock 2.4 have `lfs PROG fail` and `lfs ERASE fail` diagnostics and use the same base/4096 address calculation.

Interpreting 4096 as block size and 3008 as block count yields end address `0x01fc0000`, adjoining KVdb start. **At this point it was only a candidate interpretation.** The full live filesystem configuration and initialization path copying/referencing this table had not been captured. Do not add this entire range to read/write backing based only on constant patterns.

After checking the following, design an explicit filesystem experiment profile:

- Config passing/copying path and actual block count and read/prog/cache sizes.
- Whether mount failure calls format, format permissions/conditions, and return handling.
- Existing LittleFS version, disk format, and required assets/files.
- Observations and failure criteria distinguishing a blank test filesystem from normal stock filesystem.
- Allowed ranges separate from KVdb/NVdb, write boundaries, and atomicity. Do not fill the entire range with arbitrary FF and treat it as success.

No proprietary filesystem image or device dump was obtained. Even creating a blank filesystem does not reproduce actual stock assets, calibration data, or UI resources. Verify mount, file reads, and display separately.

## Overall status

This work narrowed the new block's cause to a LittleFS-area read. It did not bypass existing boot paths or change firmware/main/model. Full boot, filesystem mount, integrated display, and device installation/recovery remained incomplete. Product completion stayed 13/29 (44.8%), with no glasses access or persistent writes.
