# First HCI write packet and unknown trim read contract

Task bw-0274 reused actual RAM from three original mains stopped at write RDY after [virtual active event acceptance](em9305-active-event-transport.md). There was no new native start or peripheral model change. This command packet has not yet been transmitted over SPI.

## Actual prepared command

All three images prepared packet `01 01 fd 05 88 4b f0 00 08`. Nine bytes of length R8 were read from the buffer pointed to by native R10 and matched the first nine bytes of the original ROM constructor template. Previous capture/report/main/SRAM hashes and export integrity were rechecked.

| Field | Value |
| --- | --- |
| HCI packet type | `01` |
| Opcode, little endian | `fd01` |
| Parameter length | 5 |
| Start address, little endian | `00f04b88` |
| Requested data length | 8 bytes |
| SPI header | Separate `42 00` |

Thus SPI write is a transport operation sending a **memory read request** to the controller. Indexed text from the [manufacturer's EM9305 datasheet §11.2.6.1](https://www.emmicroelectronic.com/sites/default/files/products/datasheets/EM9305-DS.pdf) also defines `fd01` as EMSMM Read At Address and describes a four-byte address, one-byte length, and Command Complete response with status/data. Sending this command to a physical device was outside this task.

Stock 2.4 constructor is `0x502788`, command/response wrapper `0x501d08`, and write-capacity helper `0x50163c`. Actual addresses, pointers, and templates for the other two images are pinned in the private report.

## Response and trim dependency

The original read helper copies eight bytes from response buffer offset 7. A candidate test frame derived from the Command Complete structure in [Bluetooth Core 6.1 §7.7.14](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html) and the manufacturer's return format is 15 bytes: `04 0e 0c 01 01 fd 00` followed by eight data bytes. Command credit 1 and success status 0 here are examples, not observed actual responses.

After reading the data, the original calculates a field called trim in firmware logs: bits 7–12 of the first 16 bits, `(value >> 7) & 0x3f`. The value 7 requested by the upper caller was confirmed in actual original instructions. A source branch skips update if the value is 7 and takes a subsequent update path otherwise.

**The actual eight bytes at the address remain unknown.** The register's exact physical function and reset value, and persistence of a later update, are also undetermined. The code's trim name alone does not establish that it is an SPI clock register. Do not return `80 03 ...` matching value 7 as if it were actual state merely to make progress.

The extracted M7 fragment used synthetic values 0, `0x380`, `0x1f80`, `0xffff`, and `0x0123456789abcdef`. These are inputs for boundary and bitfield analysis, not native controller responses. Extracted values each matched actual original ARM results. If the next model handles unknown values, it must distinguish explicit data scenarios and their branch differences.

## Original write-capacity path

The helper for header `42 00` checks status `c0` and nonzero capacity and retries at most 10 times. Upper write-function source compares capacity and remaining length to split packets. Since the current packet is nine bytes, capacity 8 requires a different path from one nine-byte transmission. Actual chunk transmission was not executed here.

The original header-result-check fragment and actual GPIO-high helper were executed for 5 status/capacity combinations × retry indices 0/9 × three images = 30 cases. A noteworthy actual result: on the last retry, if status is wrong and the capacity byte nonzero, the helper can return that capacity. GPIO 149 high store also occurs then. Do not interpret this as a normal active frame. The emulator peer must check actual CS/phase as well as returned capacity. This fragment result does not prove absence of error handling across the whole host.

## Distinguishing opcode matching from status byte

The original command-wait wrapper's opcode-matching fragment also ran for five cases per image. A different opcode at response offsets 4/5 led to the boundary for another read. With the same opcode, the opcode-match fragment itself passed even with a synthetic frame with nonzero status or a different event code.

This is evidence limited to **opcode matching not substituting for status-success validation**. The whole command-wait function was not replayed, and presence or absence of all upper handling is not determined. The direct body of the read-at-address helper has no separate local status-byte branch; it copies from offset 7 and returns transport status. Thus the next peer model/verifier must not assume valid read data merely because opcode matches.

## Test scope and preservation

Original ARM fragment scenarios total 60: capacity 30 + opcode match 15 + trim extraction 15. Actual ROM instructions ran on M7 with explicitly supplied entry, stack, and registers and stopped at semantic boundaries. The GPIO helper executed the actual callee; MMIO captured a plain memory store. This is not reported as a whole-function, complete native main/HCI transaction, or physical timing test. No memory-write hook was used.

Outside Git, `~/Library/Application Support/Blackwall/simulator/`:

- `em9305-first-write-contract-01`: first actual packet/fragment analysis.
- `em9305-first-write-contract-02`: final analysis strengthened with actual caller instruction/target checks for requested trim 7.
- `em9305-first-write-verification-01`: pinned verifier and 16 dependencies, identity of prior native verification and current two model hashes, and primary source metadata.
- `em9305-first-write-contract-03`: reanalysis of the pinned copy, byte-identical to the `-02` report.

Tool: `tools/inspect_em9305_first_write.py`. Previous native acceptance/rejection verification and 190 conditions were reused after confirming identical model hashes, not rerun. Manufacturer material is search-indexed text of v4.5.3 (2025-08-20); no new local PDF/hash or visual inspection was obtained. The Bluetooth reference is the linked 6.1 section above, without a claim that it is the latest specification.

## Next work

The next unit is limited to the first `fd01` command: connect CS assert/write-ready → `42 00`/capacity → nine-byte packet → CS release → explicit Command Complete pending/read. Initial-event idle data-ready and controller readiness for host writes are different conditions. Do not unconditionally return high at a new PC.

Supply eight read-data bytes as explicit scenarios, separate from the unknown actual value. Distinguish mismatched opcode, nonzero status, small capacity, and CS abort. Actual address, command, and persistence of the later trim-update branch remain separate safety analysis. The first command being a read does not establish subsequent operations as safe or expand physical-device authorization.

Full main/BLE boot, integrated display, web installation/independent recovery, and physical verification remain incomplete. Product completion remains scope v2 13/29, 44.8%. No physical connection or write occurred.
