# EUS/ATT actual ingress and connection prerequisites

bw369, E05/E13/E14. Original firmware ATT service group, attribute lookup, permission helper, connection lookup, and dispatcher were checked. Results are **41 isolated ARM scenarios across three originals** plus actual native snapshot analysis. BLE connection and encryption state were not fabricated by the host. The specific reason ATT input does not reach TPL in current snapshots is absence of an active connection. This is not successful normal device input.

## Registered service and callback

The ATT group contains start 840/end 847, eight attributes, and read/write callbacks. The actual group linked list was read and original attsFindByHandle executed to compare attribute address/group for each of eight handles. A string search alone was not counted as successful registration. Group/attribute field layouts were also checked in original lookup/dispatch instructions.

| Target | Live EUS group | Actual registered write callback | Original EUS function |
| --- | --- | --- | --- |
| stock24 | 20006c84 | 4e3d8c | 4e3d8c |
| stock23 | 2000494c | 4d6938 | 4d6938 |
| Faceclaw38 | 2000494c | 7d5924 | 4d6938 |

The GATT value's 128-bit UUIDs share a suffix. Main original profile attributes follow. Handles are addresses for this pinned firmware/profile, not universal constants for physical devices or future versions.

| Handle | UUID identifying portion | maxLen | settings | permissions |
| --- | --- | ---: | ---: | ---: |
| 842 | 5401 (write) | 512 | 0b | 10 |
| 844 | 5402 (notify value) | 512 | 09 | 01 |
| 847 | 5403 | 1 | 03 | 90 |

Original write processor checks permission, fixed/variable length, and maxLen, and invokes group+0xc write callback when settings bit 1 is set. RAM vectors of original ATT dispatcher also showed Write Request and Write Command pointing to the same write processor. MaxLen 512 is not interpreted as current ATT MTU or guaranteed transfer length.

## Permission reference and verification level

Settings/permission constants were checked in [Arm Cordio att_api.h](https://github.com/ARMmbed/mbed-os/blob/54e8693ef4ff7e025018094f290a1d5cf380941f/connectivity/FEATURE_BLE/libraries/cordio_stack/ble-host/include/att_api.h) at pinned commit 54e8693e… (mbed-os-6.16.0). Write permission is 10 and additional write-encryption requirement 80, so 90 in the original table is write+encryption. Ordinary write 842's 10 is not treated as full app authentication. Complete version equivalence of public library and target firmware is unconfirmed.

Passing connection ID 1, write 16, and each attribute's permission to the original permission helper returned 0 for 842, 3 for 844, and 5 for 847. This is an **ABI test using an unconnected snapshot**, not actual session authorization. The actual ATT path's requirement for a valid connection before the helper was separately verified below. DM/security state was not modified to pass.

The official Mbed API documentation URL currently redirects to the GitHub organization. Constants were not settled from search cache alone: the official repository tree and six original files were downloaded outside Git. Commit/tree and Git blob/SHA256 were checked along with API constants. These are source/layout references, not copied as an execution-stack implementation. Details: private `simulator/eus-att-research-01/sources.json`.

## Faceclaw's additional wrapper

The EUS function found in bw367 is the original callback symbol; Faceclaw's actual registered pointer is 7d5924. For ordinary AA TPL input this wrapper calls original 4d6938, followed by existing 7d2638 TPL hook and original TPL fallback. Previous TPL API tests ran the last layer and did not automatically verify this wrapper.

Actual ARM ran from registered wrapper to original EUS entry, confirming preservation of seven arguments (connId/handle/opcode/offset/length/data/attribute). A separate AN prefix was confirmed only through entry to the custom-processing branch. Both are standalone callback ABI tests; neither ran ATT connection admission or custom command body. AN product functionality is not inferred from the prefix alone. Failure of the initial assumption that it equaled the original group callback is retained in source01.

## Why ATT input currently stops

The DM connection table's three slots in each snapshot have active 0, handle FFFF, and connectionId 0. Passing HCI handle 40/41 to original lookup returns 0. Passing Write Command (52), handle 842, and TPL bytes to original ATT/L2CAP dispatcher entry then returns before EUS because CCB lookup fails. Actual transmit queue increase 0 and unchanged 144-byte DM table were confirmed.

This is neither an incorrect callback address nor evidence that original firmware always rejects ordinary writes. The missing prerequisite is a connection-complete history processed by the original stack in the current virtual profile. Host does not fill pointer, connActive, or encryption bytes to enter the next function.

## 41 scenarios and limitations

- Original attribute lookup: 24 (8×3).
- Permission helper: 9 (3×3), not connected-session authorization.
- DM lookup + dispatcher no-connection drop: 6 (2×3), not successful callback delivery.
- Faceclaw wrapper normal fallback and AN boundary: 2, callback ABI boundary only.

Initial source01 failed for Faceclaw by assuming original EUS pointer was registered unchanged. Source02 confirmed actual wrapper/fallback and had 39; source03 added wrapper ABI and source04 additionally bound dispatch vector for 41. Failures and intermediate results remain. No new native run occurred; pinned main/SRAM from bw368 was used.

```sh
<private-python> tools/probe_eus_att_ingress.py <simulator> <new-private-output>
```

## Next device boundary to connect

Current EM9305 peer handles verified startup command/reply scenarios. Ready is 0 in Complete state and there is no public API to inject unsolicited runtime events. Next connect the declared virtual phone's **controller connection-complete event → SPI/readiness and necessary IRQ → original HCI/WSF/DM initialization → valid CCB → ATT input**. New controller commands after connection must also be compared with original requirements. Do not extend using arbitrary ACK/success responses.

After an actual connection is created by original code, confirm whether TPL input at GATT 842 reaches bw368's request producer. Service app→display, reply/disconnect/delay, and natural GAF/full screen remain afterward. This research does not change denominator/acceptance criteria or award progress in advance. Overall 4/16=25.0%, API checklist 3/6; no physical access, flashing, persistent write, or external publication occurred.
