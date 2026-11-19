# Original LittleFS Format and Remount in RAM

Task bw-0212. Added an execution option explicitly permitting writes to the [read-only mock volume](littlefs-read-only-blank-volume.md). In original ARM main from stock 2.4, 2.3, and Faceclaw 38, observed **first mount -84 → format 0 → remount 0 → filesystem app initialization return 0**. Execution then stopped at a GPIO input-bank read. This is not full main boot or reproduction of the stock filesystem.

## Change scope

`--littlefs-writable` requires `--blank-littlefs` and the existing blank NVdb, synthetic serial, and normal power-off configuration. It enables only `allowSectorErase` and `allowPageProgram` on the additional LittleFS RAM window. Range remains `0x01400000..0x01fc0000`; existing DB permissions, PIO model, and original main were unchanged. Omitting the option generates the existing read-only board unchanged.

Disassembled the original LittleFS app function's epilogue and confirmed `add sp,#0x28` and `pop {r4,r5,r6,pc}`, adding only a return observation point before them. This location does not change r0, allowing observation of the return value. Guest PC/registers/branches/returns were not substituted. Report field `littlefs_access` distinguishes none/read-only/read-write.

**Erase/program applies only to a RAM byte array in the simulator process.** It does not write actual glasses, disk firmware, or stock images. A complete filesystem image from the finished run was neither saved nor read from an actual device.

## Original execution results

Outside Git at `simulator/littlefs-format-main-01/`:

| Run | Format / remount / app initialization | Next blocked PC | Events |
| --- | --- | --- | ---: |
| stock24 | 0 / 0 / 0 | `0x49668c` | 3033 |
| stock23 | 0 / 0 / 0 | `0x48a7a4` | 2903 |
| cfw | 0 / 0 / 0 | `0x48a7a4` | 2995 |
| stock24-read-only | Format incomplete | Existing `0x4e8a46` erase start | 2713 |

The three writable runs had two mounts and one format. Initial mount -84 remained; format, remount, and app function each returned 0. The volume prefix also contained `littlefs` magic written by original code. This was not merely a model-generated mount success.

Mock NOR increases after the previous read-only stop:

| Input | Erase completions | Program completions | Program bytes |
| --- | ---: | ---: | ---: |
| Stock 2.4 | +7 | +21 | +5376 |
| Stock 2.3 | +6 | +12 | +3072 |
| Faceclaw 38 | +7 | +19 | +4864 |

Transfers include app filesystem initialization after format. Therefore do not interpret them as format cost alone or a patch performance difference. Specific file/call causes of differences between inputs were not yet analyzed. These are not physical power, time, or speed measurements.

Existing DB header snapshots remained, and every erase/program start reached completion. The entire previous read-only event prefix matched in new executions with zero drops. The readonly rerun matched previous CPU state, all observations, and board bytes.

## Next hardware boundary

All three writable runs were blocked on **`0x40010414` read**. According to pinned SVD address mapping this is GPIO `RD4`. The next original caller analysis must determine which pin/input condition is read. No bank value such as 0 was supplied yet. The guard's read-value field is not an observation of an actual input.

Later bw-0213's [role input contract](../power/gpio-role-input-contract.md) identified GPIO156 bit 28 and a Master/Slave selection path. Actual correspondence to left/right temples and external levels remains unverified.

Reaching this point does not mean completed RTOS boot, started BLE service, or display output. The filesystem was generated from a synthetic blank volume; existence of stock files, fonts, UI assets, or device calibration data is not guaranteed.

## Verification and records

- Preserved CLI rejection before the option existed in `littlefs-writable-red-01`. This confirms option absence, not format behavior.
- Two prerequisite CLI cases were rejected before output-directory creation.
- Four actual original-main runs: three writable and one default readonly. Core/peripheral models were compared as byte-identical to earlier versions.
- `verify_littlefs_format_evidence.py`: 87 checks of actual logs/reports, pinned main/derived assets, prior event prefix, original returns, magic, completed erase/program, default read-only behavior, and next block.
- Python compilation passed.

Result: `littlefs-format-verification-01/report.json`. A review agent inheriting the parent model compared bw0211 backup and helper diff read-only and found no material defects. It confirmed permissions applied only to the child, default RO remained, and epilogue observation preserved r0. Other native and RO-preservation results were checked by the audit above. Astra was not used.

## Overall status

Confirmed format, remount, and app filesystem-initialization return on a synthetic RAM volume. Next compare the caller, pin, and input meaning of GPIO RD4 access with source. Full main boot, BLE, integrated display, and physical installation/recovery remained incomplete; product completion stayed 13/29 (44.8%). No glasses access, persistent write, or external publication occurred.
