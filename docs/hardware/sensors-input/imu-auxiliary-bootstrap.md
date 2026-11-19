# IMU auxiliary interface initialization

bw-0329. Connected pad and interrupt configuration after [power/FIFO initialization](imu-power-fifo-initialization.md). Original main from stock 2.4, 2.3, and Faceclaw initialized the auxiliary sensor transport object and advanced to the internal I²C master's first setting, `A20F=1E`. This write stopped at an unsupported boundary; it does not mean auxiliary sensor communication completed or an ID was received.

## Configuration performed by the original

| Target | Original behavior | Scope preserved/allowed by model |
| --- | --- | --- |
| pad register 30 | `(old & f3) \| 14` | bit 4=1, bit 2..3 field value 1, remaining bits preserved |
| Read INT1 config 16/17 | Expand 2 bytes into 15 booleans | byte 17 bit 7 absent from structure |
| Write config | Set structure index 13 to 1 and reconstruct 2 bytes | Set byte 17 bit 5, clear bit 7 to 0, preserve other bits |

The INT setter builds two bytes from 15 fields without a separate read and writes the final reserved bit as 0. Do not assume it preserves all 16 bits unchanged. Subsequent transport initialization installs the original read/write callback pointers and maximum read 21 bytes/write 6 bytes in SRAM. This object and the first master command were also confirmed in actual native SRAM.

Original MAG initialization checks ID 45 in register 01 after unlocking and reset. An independent ARM fragment selected the next call for only ID 45 out of 256 IDs. This is distinct from a native run actually receiving an ID.

## Limited model and execution

`auxiliaryConfigurationHex` specifies three initial bytes for pad 30 and INT1 config 16/17. `BlackwallImuAuxiliarySetup` is selected only after reading two pairs of state snapshots. After a read lease it accepts only the observed pad request and INT1 bit change and rejects other bit changes. Reset restores the three bytes, leases, and counters. I²C master execution, IRQ generation, magnetometer data, and ODR are not implemented yet.

| Input | Initial pad/config16/config17 | Original saved result | Next unsupported request |
| --- | --- | --- | --- |
| Stock 2.4 | `a5/b6/d7` | `b5/b6/77` | `7c a2 0f 1e` |
| Stock 2.3 | `a5/b6/d7` | `b5/b6/77` | Same request |
| Faceclaw | `a5/b6/d7` | `b5/b6/77` | Same request |
| Stock 2.4 control | `5a/39/a2` | `56/39/22` | Same request |

Each run confirmed one pad read/write, one INT pair read/write, 72 successful I²C finishes, and 29 received bytes. The prior event prefix of every normal run was preserved. The disabled control exactly matched CPU state and all observed events from the earlier power/FIFO-only run. No original ARM instructions, branches, return values, or CPU hooks were added or changed.

The first master request is a composed write sending four bytes at once. A check that reused the descriptor offset of an earlier one-byte request failed and was preserved. Following the original HAL's 10-word push and 0x28-byte local frame and the caller's explicit descriptor argument `sp+0x20`, address 69, length 4, write direction, and payload were checked at current `SP+0x70`. Current `SP+0x50` is the packet buffer in this case, not the descriptor. The emulator or guest execution was not changed to fit the check.

## Identification evidence and additional official material

The filename `imu_icm45608.c` was found in all three binaries. The omission from the earlier uppercase-focused search was corrected in the [IMU device expectation document](imu-device-expectation.md). This binary string is source evidence, not a reading of physical markings or revision.

Seven files at pinned TDK commit `646f55a6ec119b59d9ebce47af660842b53e5506` were verified against canonical Git tree blob SHA1 and download SHA256:

- `src/imu/inv_imu_i2cm.c`, `.h`
- `src/invn_mag.c`, `.h`
- `src/Ict1531x/Ict1531x.c`, `.h`, `Ict1531xSerif.h`

The wrapper's secondary address 1e and driver's ID 45, register 01, and unlock/reset sequence match the observed original. The SDK itself does not guarantee G2's entire ABI, initial values, or physical behavior. The repository LICENSE is the previously verified BSD-3-Clause, and each file's InvenSense permission/as-is header was preserved unchanged. These were added to a separate private research folder without modifying the existing TDK source snapshot.

[TDK DS-000548 revision 1.1](https://d17t6iyxenbwp1.cloudfront.net/s3fs-public/2026-08/ds-000548-ict-15312-ict-15318-datasheet-v1.1.pdf) also defines register 01/ID 45 and the same unlock/reset. Since it covers both ICT-15312 and 15318, the ID alone does not select a variant. The original PDF and hash were preserved as private assets. Physical magnetometer identification remains incomplete.

## Verification and remaining path

`inspect_imu_auxiliary.py` checks 256 pad values, INT getter/error, packer, and ID gate in 4,728 independent ARM fragments across the three images. The first report contained an error including a global data pointer in callback metadata and was preserved; source02, limited to code pointers, was used as the final version. The two callbacks in final metadata also matched Thumb pointers in actual native SRAM.

Unit 151 and frozen 151 report values matched. Source 4,728 and frozen 4,728 passed, and the two reports/inspectors were byte-identical. Python 475 matched frozen source and passed syntax checks. Nine existing peripheral models were unchanged and one IMU peer extended. This is not a functional test of every tool.

Five valid native runs, five saved audits, and four actual state/descriptor/transport object checks are preserved in private `simulator/imu-aux-verification-01/manifest.json`. The common planner's previous six paths were identical except for the current model SHA.

Next, model the acquired official I²C master driver together with original command encoding, completion flags, and error handling, and execute magnetometer ID/reset. Then continue deferred ODR initialization and nonzero main draw, framebuffer/576×288 viewer. MAG communication, ODR, sample/IRQ, and full boot/UI remain incomplete. Overall 13/29=44.8% and scope v2 are maintained; there is no physical connection, installation, or persistent write.
