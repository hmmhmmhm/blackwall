# First IOM5 Transfer and Touch Driver Query Path

Work `bw-0234`. The IOM5 command after [TIMER7 initial configuration](timer7-pwm-model.md) was investigated and pointer-transfer diagnostics connected without fabricating responses. Pinned original ARM for stock 2.4, stock 2.3, and Faceclaw38 ran from reset. No physical access, flash, OTA, MRAM write, or touch-device write occurred.

## Confirming the first request

The existing source-derived IOM already supports I²C/FIFO/polling transfers but blocks commands without a registered peer. The existing stop was not simply an unimplemented CMD register: it was **absence of a peer registered at IOM5 address `0x0c`**.

After stopping, the common runner and `tools/iom5-first-request-candidate.json` read DEVADDR and SRAM descriptor/buffer. Hooks, model, and board were unchanged during execution. DEVADDR read is host diagnostics and increments IOM5 Reads by 1. Normalizing that one read makes previous CPU/instruction count/state exact across all three inputs and all observed events match. The diagnostic read is not counted as firmware-executed.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| First CMD PC | `0x58236c` | `0x57b014` |
| Target | IOM5, I²C `0x0c` | Same |
| CMD | `0x101`: write, length 1 | Same |
| Descriptor | `0x2034aef8` | `0x20369550` |
| TX buffer | `0x2034af48` | `0x203695a0` |
| Buffer word | `0x00000001` | Same |

Descriptor address/length/TX pointer were compared with offsets 0/0x10/0x18 used by the actual ARM callee. Other descriptor field meanings are not arbitrarily established. Results are outside Git in `iom5-first-request-01`.

## Pointer-only diagnostic peer

`BlackwallIomRegisterProbe` in `renode-iom-register-probe.cs` is explicit IOM5 profile `pointer-01-only`. It accepts exactly one byte `01` and records a pointer. Virtual ACK is **a diagnostic assumption, not verification of actual device ACK**. It rejects other pointers, empty writes, and data writes, and stops all reads. It returns no ID, version, sensor, or touch data.

Only a diagnostic method forwarding peer-unsupported accesses to the existing IOM strict guard was added to `renode-iom.cs`. Default peer connection and transfer rules remain. The profile connects only on the board in `tools/iom5-pointer-candidate.json`. Transfer completion/IRQ are handled after the existing FIFO engine actually consumes transmitted bytes. No arbitrary completion bit or forced guest branch/return is used.

Native TDD first confirmed missing peer type. After implementation, 18 unit items verified pointer reception, original completion/IRQ, W1C, no-response stop on unknown read, no RX/completion generation, distinction between controller reset and peer reset, and rejection of other addresses/invalid writes. Existing IOM 82 items also passed. The existing test's image tag was confirmed equal to current pinned image SHA. Unit one-byte-read counterexample and original four-byte request below are different checks.

## Original next request

Three original inputs with pointer-only peer selected completed the first write, then attempted a **four-byte read from register 1**. Read stopped before returning information.

| Input | Read CMD PC | Actual CMD | Peer record |
| --- | --- | --- | --- |
| Stock 2.4 | `0x582242` | `0x402` | pointer 1, write 1/finish 1, read attempt 1/count 4 |
| Stock 2.3 | `0x57aeea` | Same | Same |
| Faceclaw38 | `0x57aeea` | Same | Same |

IOM Commands=2 counts **one completed write plus one stopped read attempt**, not two completed transfers. Strict record is IOM5 CMD address `0x40055120`, operation=`peer-read`, value=4. Value 4 diagnoses read length; original CMD was separately confirmed as CPU R2=`0x402`.

Previous event prefix, UART0 bytes, and original eight IRQs were preserved for all three inputs. Stock 2.4 control without peer exactly matched prior CPU/instruction count/events/stop point. Results are `iom5-pointer-main-01`. Full SRAM, schedule, and physical timing equivalence are not established.

## Touch-driver evidence and hypothesis correction

Based only on address `0x0c` and pointer 1, AK09918 WIA2 query was considered. [AKM AK09918 datasheet](https://cdn.sparkfun.com/assets/d/a/e/4/5/AK09918C_Datasheet.pdf) defines that address and a one-byte identification register. The original requested four bytes, however, and surrounding original code connects to the touch driver below. Therefore **this first transfer is not modeled as an AK09918 ID query**. No response tailored to that candidate was supplied.

Stock 2.4 callback `0x4fba0c` calls the common IOM5/address 0x0c read wrapper, and registration function `0x4fbcd2` connects that callback. The same module's literal pool contains `driver\\touch\\drv_cy8c4046fni.c` and `_cy8c4046fniReadGestureCfg`. Helper `0x4fba7c` connects to register 1/read 4, and original ARM at `0x4fbe98` assembles four bytes into a big-endian 32-bit value. The equivalent stock 2.3/CFW decoder is `0x579738`.

Twelve isolated unmodified original decoder runs (three inputs × four vectors) confirmed assembly such as `01 02 03 04 → 0x01020304`. This uses synthetic inputs to check conversion semantics; it did not obtain or return an actual touch version. Strings, callback, and decoder are **source evidence of touch-driver connection**, not evidence of exact physical CY8C4046FNI suffix/revision/current firmware identity. Original code also has touch firmware version comparison/DFU strings, but the complete consumer/update branch for this first value has not been analyzed.

## Audit and next work

The 253 items in `iom5-first-transfer-verification-01/audit.py` checked pinned mains, component changes, model/board, actual logs/reports, snapshots, events, off control, unit/regression, and 12 original decoder cases. Input SHAs and candidate source were preserved together; the audit does not depend on current model builder or new native runs. Python compilation was also checked.

Next investigate the actual touch-version query consumer, legitimately obtained touch firmware package/metadata, and version-mismatch/DFU branches together. Do not provide unverified four bytes as a success value or fill remaining touch registers with generic ACK/0. Later model version responses must clearly distinguish actual values from package-based synthetic scenarios.

Web integrated installation (W5), original app loop (S6), normal font-bank/integrated display (D3), and physical installation/recovery remain incomplete. Overall product fulfillment is 13/29 (44.8%).
