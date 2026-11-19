# NVM boundary of BLE version read and trim update

Task bw-0276 reused saved original M55 runs and SRAM from the [first read transfer](em9305-first-read-command-transport.md). **Trim update is not merely a temporary register setting: original code prepares page erase and write in the EM9305 information area.** Current physical controller values, backup, and recoverability remain unconfirmed. No new native main run, device connection, or controller command transmission occurred.

## Levels of confirmation

- **Saved native evidence:** after the first trim read with virtual value 7, stock 2.4/2.3/Faceclaw38's next pending packet was `01 01 fd 05 00 20 40 00 04`.
- **Original code and extracted execution:** constructors for the next packet and trim modification/erase/write, and status/version-log/error-return fragments ran in isolation as actual ARM instructions. All three images showed the same packets and branches.
- **Manufacturer material:** command/memory regions were compared with current URL search-index v4.5.3 (2025-08-20), §11.2.6.3/7, §11.3, and Figure 10-4. No local PDF/hash or new visual PDF verification was obtained.
- **Unconfirmed:** actual controller data, complete NVM contents, lock/authentication state, physical erase/write outcomes, and recovery from interruption. ARM fragment tests are not a natural main run through the whole trim function.

## Meaning of the second read

In stock 2.4, wrapper `0x5025de` passes address `0x00402000`, length 4, to generic fd01 helper (`0x502124`). The upper caller prepares `BLE FW Ver: %d.%d.%d.%d` from returned data. Log numbers are ordered from high to low byte of the 32-bit value. It logs when transport succeeds and value is not `ffffffff`; zero also logs as `0.0.0.0`. This does not mean an actual version value was obtained.

After transport success, the generic read helper checks status at response offset 6 and copies the requested byte count from offset 7 on success. This differs from the direct body of the previously analyzed trim-specific getter. Opcode matching or a version log alone does not establish complete BLE initialization.

## Actual trim-update sequence

When trim extracted from the current RF register differs from target 7 or the force argument is set, the original call graph proceeds as follows. Addresses are controller addresses, not Apollo MRAM addresses.

| Order | Operation prepared by original | Packet or data |
| --- | --- | --- |
| 1 | Repeat GPIO93 reset and GPIO15 pulses, wait for configuration-mode event | Expected event `04 ff 01 03` |
| 2 | Read eight candidate manufacturing-data bytes | `01 01 fd 05 a0 7c 40 00 08` → `0x00407ca0` |
| 3 | Modify trim field of the eight read bytes | Replace only byte 4 bit 7 + byte 5 bits 0..4 |
| 4 | Erase NVM information-area page 2 | `01 07 fd 02 01 02` |
| 5 | Write 16 bytes at `0x00405c80` | fd03, header word 2 + CRC32 + modified eight bytes |
| 6 | Retry existing active-state initialization | Call initialization helper |

[Manufacturer datasheet §11.2.6.7](https://www.emmicroelectronic.com/sites/default/files/products/datasheets/EM9305-DS.pdf) defines fd07's two arguments as area/page, with area 1 as information. §11.2.6.3 defines fd03 as address-specified write. Figure 10-4 places page 2 at `0x404000–0x405fff` in customer data and page 3 in manufacturing data. Thus code's read address lies in page 3 and program address in page 2. Do not reduce erasing all of page 2 and writing some data to a simple eight-byte change. There is no evidence that remaining page-2 contents on this device are unnecessary or recoverable.

The original checksum function actually ran and was compared with independent `zlib.crc32`. For synthetic input `01 23 45 67 89 ab cd ef`, packet was `01 03 fd 14 80 5c 40 00 02 00 00 00 ae d1 c7 28 01 23 45 67 89 ab cd ef`. This is a synthetic constructor test, not a physical-device image or transfer instruction.

Configuration-mode event 03 and active-state event 01 are distinct. A new static check initially expected them to match and failed against the actual original template; it was corrected to `04ff0103`. Previous rejection of event 03 in the wrong-active-event test remains valid. Do not generalize initial active-path rejection to every reset path. [Manufacturer §11.3](https://www.emmicroelectronic.com/sites/default/files/products/datasheets/EM9305-DS.pdf) also distinguishes the two subevents.

## Error-reporting limitations

Trim routine initializes r4 to 0. Isolated execution of original return fragments after the diagnostic logger prepares 1 for reset error and 5 for reinitialization error, but some first-read/factory-read/erase/program error exits retain 0. This is a result for **error-exit fragments with explicit r4=0 input**. It is not evidence of integrated execution of entire error paths, actual HCI status, and logging. It does not alone establish that all calls falsely report success.

Nevertheless, future simulator/safety checkers must not declare NVM update successful solely from routine return 0. Check exact opcode/status, erase/write targets, read results, and reinitialization events separately. Do not assume the generic read's status check exists in other dedicated helpers.

## Verification and preservation

`tools/inspect_em9305_trim_reset.py` is the new analyzer. Per image: constructor 4 + trim bitfield 9 + generic read status 6 + version log 8 + trim error exit 6 = 33 conditions, **99 original ARM scenarios** across three images. Original memset/copy/checksum executes and stops before actual transport calls or branch boundaries. Synthetic entry/stack/registers and M7 are used; peripherals/NVM do not execute. There are no write observers, success stubs, or forced branches.

Private simulator `em9305-trim-reset-contract-01` is initial 57-condition analysis, `-02` adds version for 81, `-03` adds error exits for 99, `-04` checks call order and initial r4, and `-04a` is the authoritative version adding pinned original-main hash checks. The two reports match. Failed reset-event expectation is retained in subsequent verifier notes. `em9305-trim-reset-verification-01` pins analyzer dependencies, original main/SRAM/prior native evidence, and source provenance. A pinned-copy `-05` is produced to compare report identity with the authoritative version.

## Safety and next implementation

- Current experiments use only files and virtual CPU memory outside Git. Glasses and controller NVM were not changed.
- Full stock recovery scope must include **changed EM9305 NVM** as well as Apollo main/boot. There is no evidence that Apollo MRAM restoration restores controller information area.
- Actual trim, controller-info backup scope, legal/security preservation, other page-2 data, lock state, and recovery from interrupted erase need separate confirmation. Even read-only inspection is not performed without device-specific authorization.
- The next simulator unit handles version-read status/data/log as explicit unknown fixtures and models the trim-mismatch branch as a separate **configuration-mode reset → factory read → virtual NVM erase/program → active reinitialization** transaction. Do not eliminate that path with an arbitrary trim-7 value. Virtual NVM is not connected to host devices or physical transport.

Product progress is **13/29=44.8%**. Main/BLE boot, integrated display, and physical recovery remain incomplete; the hardware authorization boundary remains.
