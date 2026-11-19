# Read-Only Synthetic LittleFS Volume

Task: bw-0211. Connected a blank synthetic volume only in the confirmed range `0x01400000..0x01fc0000`. Original main from stock 2.4, 2.3, and Faceclaw 38 **returned -84 from the first mount and entered format**. The model rejected the read-only volume's first sector erase. This is not a successful mount or completed format.

## Separating data and permissions

Added optional `AdditionalWindow` to `BlackwallNorReadWindow`. The existing root retains KVdb/NVdb range and write permissions; the additional window has its own byte array, range, and erase/program permissions. The LittleFS window here is read-only RAM initialized to FF. No stock filesystem, device dump, or actual user files were used.

The constructor rejects overlapping ranges and additional children on an additional window. A read must fit entirely within one window. Every target byte after page wrap for program must be in the same window; erase must also fit an entire 4,096-byte sector within one window. Only that window's permissions are then applied. Root DB write permissions are not inherited by LittleFS. Requests spanning both ranges are not partially applied. Reset preserves committed RAM bytes under existing policy.

The volume attaches only with explicit `--blank-littlefs`, which also requires blank NVdb, synthetic serial, and normal CRYPTO/OTP off profiles. It is unattached by default. The standard NOR marker's start/length point to the existing primary DB window; read counters total all PIO transfers. A separate `BLACKWALL_LITTLEFS_VOLUME` marker records additional range, permissions, FF prefix, and synthetic status.

## Original execution

With an initial RX limit of 256, the 16-byte read advanced but the next 4,096-byte cache read was rejected at `CTRL=0x10000461`. This result is preserved in `littlefs-blank-main-01/stock24`. To match the original request and config's 4,096-byte cache, explicitly set the existing bounded FIFO streaming RX limit to 4,096. The default limit and PIO timing model were unchanged.

Results in `littlefs-blank-main-02/` outside Git:

| Run | Original result | Block |
| --- | --- | --- |
| stock24 | mount -84 → format entry | PC `0x4e8a46`, sector erase start `CTRL=0xe1` |
| stock23 | Same | PC `0x4db672`, same |
| cfw | Same | PC `0x4db672`, same |
| stock24-default | Additional window unattached | Existing 16-byte read start `CTRL=0x100461` |

Each of the three volume-attached runs had one first mount and one format entry. Format return and remount return were each zero occurrences, not yet reached. Final INSTR=`0x20`, ADDR=`0x01400000`; with write enable set, **start was rejected because the additional window lacked erase permission**. Erase/program completion counts and programmed DB-byte results matched prior runs. No erase/program was performed on the new volume.

Array reads increased by five and 8,240 bytes over the prior run; the last array address was `0x01401000`. Read sizes included 16-byte and 4,096-byte paths. These are mock transfer amounts, not measured BLE/flash performance. There were 2,713 observation events, zero drops, and the entire prior event prefix remained after excluding new LittleFS observation points. Main bytes, main-reset entry, branches, and return values were unchanged.

The default unattached run retained the prior CPU boundary and all selected events. The option therefore did not expand default behavior.

## Verification

- Pre-change red: unsupported additional constructor argument saved in `nor-additional-red-01/renode.log`.
- 31 window checks: range/boundary reads, independent permissions, page wrap, reset preservation, overlap/chain rejection, and split program/erase rejection with data unchanged on both sides.
- Existing 46 array-read and 29 page-program regression checks; 106 total.
- Five original runs: one RX-256 limit, three RX-4096 plus blank, and one unattached default.
- One prerequisite CLI case rejected before output-directory creation.
- 93 checks in `verify_littlefs_blank_evidence.py` compared actual logs/reports, current model, pinned main/derived assets, prior event prefix, -84 return, incomplete format, erase target, unchanged DB program/erase, and default boundary.

Result: `littlefs-blank-verification-01/report.json`. Python compilation also passed.

A read-only review agent inheriting the parent model reported no Important/Critical findings. Its suggestion to strengthen direct split program/erase checks was incorporated. The erase test first wrote different non-FF bytes on both sides and checked they remained after rejection. Astra was not used.

## Next steps and overall status

Later bw-0212 connected a [separate RAM write option](littlefs-format-remount-ram.md) and confirmed format 0, remount 0, and app initialization 0 in all three originals. The default read-only boundary remains. The following describes next steps at the end of bw-0211.

Next attach an experimental profile explicitly allowing RAM erase/program only in the confirmed mock-volume range and verify original format/remount results. This is not approval to format a physical device, and failed returns must not be replaced with success. Even a formatted blank volume does not imply stock assets or required files exist. Next check file requirements and display asset paths.

Overall product criteria were 13/29 (44.8%). Completed filesystem mount/format, full boot, integrated display, and physical installation/recovery were incomplete. There was no glasses scan/connection, RAM payload, persistent write, OTA, flash, or external publication.
