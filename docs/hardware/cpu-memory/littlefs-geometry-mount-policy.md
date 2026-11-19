# LittleFS Active Configuration and Mount Failure Policy

Task: bw-0210. Compared the configuration candidate from the [prior read contract](post-nvdb-mspi-read-contract.md) with original execution. Stock 2.4, 2.3, and Faceclaw 38 all use that ROM table as active config, and the configured block count stored by the original in the state object is 3,008. Combining block-address calculation with the table's 4,096-byte block size yields the configured range **`0x01400000..0x01fc0000`**, end exclusive. Actual filesystem contents and successful mount were not confirmed.

## Original code and execution evidence

`inspect_littlefs_mount_policy.py` checks 55 items across three pinned main inputs. App initialization passes a ROM config and SRAM state object to the first mount. Initialization inside mount stores the r1 config pointer at state object+`0x68` and the value at config+`0x20` at state object+`0x6c`.

| Location | Stock 2.4 | Stock 2.3 / Faceclaw 38 |
| --- | --- | --- |
| App LittleFS initialization | `0x48336c` | `0x4809b8` |
| Config installation function | `0x4f374c` | `0x49afa0` |
| Active ROM config | `0x6f0214` | `0x70df68` |
| SRAM state object | `0x20073be8` | `0x20074834` |

`probe_littlefs_config.py` copies existing original-main execution inputs and adds only mount, format, and read callback observation points. At the first read callback, it adds a snapshot reading two words at state object+`0x68`. It does not write guest memory/PC/registers. No new flash backing or read value is supplied.

The first read callback's r0 was the config address above for all three inputs, and the snapshot was `[corresponding config address,3008]`. Mount and read callback each ran once; format entry ran zero times. Because the first volume read was unsupported and mount had not returned, this does not mean format was unnecessary.

The entire existing CPU stop state and prior 2,699 observation events matched in each run. Including two new mount/read events gives 2,701 with zero drops. The format observation point did not execute. Eight items per case across three runs yielded 24 checks. There was no new model or function reimplementation.

Results outside Git:

- `littlefs-mount-policy-contract-01/report.json`: 55 source checks.
- `littlefs-config-main-01/{stock24,stock23,cfw}`: actual original-main execution, eight checks each.
- `littlefs-geometry-verification-01/report.json`: aggregate of 79 checks. Logs/reports, derived asset hashes, and current model bytes were compared again.

## Original policy on mount failure

The app initialization branches as follows:

1. If the first mount returns 0, skip format.
2. **If the first mount returns any nonzero value, call format.** It does not check only a particular corrupt error.
3. Call mount again with the same config without checking format's return r0.
4. If the second mount fails, log a diagnostic and return 9. The original diagnostic string describes format failure, but the actual checked result is the second mount.
5. If the second mount succeeds, proceed with subsequent initialization.

This is a **call policy** established by static code. Failure, format, and remount did not complete in this execution. It does not establish successful format, recovery from interruption, or filesystem integrity. Directory initialization and subsequent file operations also follow app initialization; passing only the first mount does not complete all initialization.

## Boundary for applying a mock volume

Existing synthetic KVdb/NVdb backing is `0x01fc0000..0x02000000`. The confirmed LittleFS configured range directly adjoins it. The next implementation treats this range as an explicitly selected **isolated synthetic filesystem experiment**, preserving the default unsupported boundary.

- First verify read ranges, boundaries, and failure observations, and check how the original mount handles a blank volume.
- If the original attempts format, explicitly specify mock erase/program authorization and ranges within RAM separately. This is not authorization to write or format a physical device.
- Distinguish a blank or newly formatted volume with no actual files/assets from a stock filesystem. Do not replace missing assets/files with success responses.
- Limit geometry to the current three main configurations. Do not apply it automatically to other firmware/hardware combinations.
- Check that read/program/erase boundaries do not leak into KVdb/NVdb or beyond permitted ranges.

On actual devices, a mount error can lead to a format call, so do not run this path on a device arbitrarily. This work involved no glasses scan/connection, RAM payload, persistent write, OTA, or flash.

## Overall status

Later bw-0211 connected a [read-only synthetic volume](littlefs-read-only-blank-volume.md). It observed mount -84 and format entry in all three originals and blocked the first erase. The incomplete items below describe the end of this configuration analysis.

LittleFS configured range and mount-failure policy were established. Filesystem backing, completed mount/format, required files/assets, full main boot, and display output remained incomplete. Product acceptance criteria stayed 13/29 (44.8%).
