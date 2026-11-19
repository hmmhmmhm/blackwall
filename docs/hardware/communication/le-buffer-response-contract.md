# Original consumption of LE buffer information and short return data

bw-0290. Original ARM functions were executed from the prior natural main `2002` waiting snapshot. There was no new native main, peripheral model, or web gate change. Overall 13/29=44.8%, full boot, and integrated display remain incomplete.

## Normal response format

LE Read Buffer Size v1 returns one-byte status, two-byte ACL data length, and one-byte packet count, so H4 Command Complete is 10 bytes. Distinguish the shared BR/EDR buffer path allowing packet count 0 from rules for an LE-only controller. [Bluetooth Core 6.1 §7.8.2 and §4.1.1](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-61/out/en/host-controller-interface/host-controller-interface-functional-specification.html). Actual EM9305 length and packet count were not established here.

## Original stores and getter

After checking opcode, the original initialization callback skips status and stores following length and packet count in the fields below. Observed stores are one uint16 length and two uint8 packet counts. The two packet-count fields are initially filled with the same value. Available/maximum credit roles are plausible, but actual ACL transmission, decrement, and completion events have not verified them.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| Initialization callback | `5a3d12` | `5880de` |
| Length field | `20073146` | `20073f3e` |
| Packet count A | `2007314a` | `20073f42` |
| Packet count B | `2007314b` | `20073f43` |
| Original length getter | `56485a` | `54ce5c` |

Length 27/count 4, 251/8, length 0, count 0, both 0, marker values, and 16-bit/8-bit maxima were tested separately. For every selected complete response, original fields and getter reflected supplied values unchanged and the next `01 1c 20 00` query was prepared. This is not evidence of validity, physical support, or safe ACL transmission for those values. With status 1, supplied values were also stored and the same next command prepared.

## Two distinct kinds of short response

When the last byte of the ten-byte wire response was missing, the H4 parser had not yet delivered a complete packet. The three fields remained unchanged and no next command appeared. Unknown opcode and no-event controls also changed neither fields nor subsequent queue.

In contrast, `04 0e 04 01 02 20 00` has complete H4 framing but lacks the three information bytes required by this command. The original callback's read start is raw event pointer+6, also the declared event end. It read the following three bytes from backing RAM and stored them in length/packet-count fields; the getter returned those values and the next query was prepared.

The test did not place arbitrary values in padding. It used the packet created by the original parser and residual contents of existing SRAM. This observes a read beyond the declared input end; it does not prove the entire heap boundary, physical controller response, actual memory corruption, or a physical vulnerability. There is no basis to conclude this callback sufficiently checks command-specific return length. A future virtual peer must not generate such a short return as a normal response.

## Observation equivalence

Twelve scenarios were run on each of three images: 36 logical scenarios including normal, zero, maximum, error, incomplete, unknown, and no-event. All are Unicorn M7 executions with synthetic entry/register/stack and verified native SRAM, not additional successful natural Renode boot.

Additional code observer off/on was compared in every scenario. The observer reads callback packet header, R4 data pointer, and registers immediately before three known stores; no memory-write hook was used. All 36 pairs matched in phase PC trace hash, general/special registers, complete SRAM, WORK, and passive SCS memory. Observed store locations/values and final fields were also compared. This is not expanded to complete transient write history at all addresses or a neutrality guarantee for other observers.

Initial diagnosis failed to find stores because it distinguished `strh.w`/`strb.w` from `strh`/`strb`. The final contract checks actual original instructions and PCs including `.w`.

## Preserved material and next work

Recorded in `tools/inspect_le_buffer_contract.py` and outside-Git simulator `le-buffer-source-01`, `-02`, `le-buffer-verification-01/manifest.json`. Reanalysis report with 37 pinned Python copies matched. The second execution extended observer comparison to special registers and SCS and passed. Four models and web source match prior SHAs.

The next virtual initialization extension must distinguish actual chip information from explicit mock length/packet counts. For example 27/4 and 251/8 can be different assumed profiles, but must not be labeled physical values. Verify actual credit use and ACL fragmentation on separate original paths. Connect the next `201c` information response only after confirming original expected length and consumption. The natural app loop/display initialization and original glyph/GPU integration goals remain. No glasses/case access, flash, OTA, or persistent write occurred.
