# Revision Branches in Power Management Initialization

Status: Offline execution of pinned actual main binaries. This is not confirmation of the user's device revision or validation of normal boot or power behavior.

The [public Ambiq SPOT manager](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/am_hal_spotmgr.c) calculates internal classification flags from chip revision and trim version; for some combinations it uses PATCH_TRACKER0 bit 0 to distinguish absence of a patch. A prefix with the same conditions was found in actual G2 code. Function and flag names are research names based on correspondence with the public HAL; original G2 debug symbols were not obtained.

## Scope confirmed by isolated execution

`tools/emulate_spot_flags.py` validates bundle SHA and component CRC before executing the following segments:

| Image | Entry | Stop before power configuration | Trim cache | Tracker cache |
| --- | --- | --- | --- | --- |
| Stock 2.3 / Faceclaw 38 | 0x489c34 | 0x489d7e | 0x200001ec | 0x20074768 |
| Stock 2.4 | 0x495b1c | 0x495c66 | 0x200001f0 | 0x20073b1c |

The CHIPREV read and both caches are explicit synthetic inputs. The trim cache value is not assumed identical to the original Info1 TRIM_REV word; the earlier conversion that populates the cache is outside this test. Only initialization of 60 context bytes is handled by a substitute function. Guest writes are limited to four stack words from function PUSH and six classification-flag bytes; MCUCTRL writes are rejected.

For each image, CHIPREV=0x21/0x22/0x23/0x24 × trim cache=0/1/2/3 × tracker cache=0/1 were executed, totaling 96 conditions. All six classification flags matched the expected conditions. The Faceclaw prefix is identical to stock 2.3, including SHA-256.

In particular, actual instruction execution confirmed:

```text
pcm21 = (chipLow8 == 0x22 && trimCache == 2)
     || (chipLow8 == 0x23 && trimCache == 1)
pcm21_without_patch = pcm21 && ((trackerCache & 1) == 0)
```

The reason the earlier absolute-address search failed to find tracker use was also identified. Around 0x489d64, 2.3 adds offset 0x34 to literal base 0x20074734 to read 0x20074768. Thus absence of the final absolute-address word in raw main was not evidence that the cache is unused. The bit 0 check left unknown by the earlier investigation is confirmed within this limited prefix, but the actual device's bit value remains unknown.

The report is outside Git at `Blackwall/simulator/spot-classification-01.json`. It does not prove power configuration register operation, execution after handler selection, or official bootloader patch compatibility.

## Optional model applied to the main reset runner

`--chip-revision-fixture 0x21|0x22|0x23|0x24` is selected together with the MCUCTRL model. It supplies only aligned four-byte CHIPREV reads and stops on partial-width reads and writes. SIPART and upper bits are assumed zero; the report retains `hardware_verified=false`. If the model is not selected, execution stops at the CHIPREV read as before.

The four scenarios from `startup-zero-info1-rev-21-hypothesis` through `...-24-hypothesis` combine only the existing virtual power state, three Info1 zero fixtures, and CHIPREV assumptions. Stock 2.4 main reset CLI was run with each scenario.

| CHIPREV assumption | Next unimplemented access | PC |
| --- | --- | --- |
| 0x21 | Read 0x40021018 | 0x494964 |
| 0x22 | Read 0x40020028 | 0x495c7e |
| 0x23 | Read 0x40020028 | 0x495c7e |
| 0x24 | Read information word 0x42003370 | 0x48 |

These results compare branches under synthetic metadata. They do not establish which of the four combinations an actual G2 has, whether calibration/voltage configuration is valid, or whether the init handler completes normally. Reports are outside Git in `Blackwall/simulator/chiprev-hypotheses-01/`. Fifty-two runner tests and three scenario tests passed.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" tools/emulate_spot_flags.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01" \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-spot-flags.json"
```

Full simulator boot/display transport integration and actual web installation/recovery validation remain incomplete.

## Restricted storage of observed power settings

After the prefix above, code around `0x489d94` in 2.3/Faceclaw and `0x495c7c` in 2.4 performs read-modify-write on ACRG and VRCTRL. According to the [public MCUCTRL definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/mcuctrl_regs.html), ACRG 0x40020028 bits 0/1 are software enable/power-down, and VRCTRL 0x40020060 bits 15:13 control ANALDO.

`--spot-control-storage` supports only storage and readback of these values:

| Register | Virtual initial value | Allowed stored values |
| --- | --- | --- |
| ACRG | 0x78 | 0x78, 0x79 |
| VRCTRL | 0 | 0, 0x8000, 0xc000, 0xe000 |

The ACRG initial value is a test fixture reflecting documented reset trim bits, not an observation of the actual device's initial or valid calibrated value. Initializing it entirely to zero would erase documented trim bits, so that was not done. Unobserved field values, other registers, and partial-width accesses stop execution. SWE gating and actual power, voltage, and stabilization time are not modeled. Reports retain `analog_power=not-modeled` and `hardware_verified=false`.

`startup-zero-info1-rev-22-spot-storage-hypothesis` and `startup-zero-info1-rev-23-spot-storage-hypothesis` explicitly add this storage option. Existing scenarios were not changed. Six CLI runs covering stock 2.3, 2.4, and Faceclaw 38 × both scenarios completed. All recorded two ACRG reads and writes each with final value 0x79, and three VRCTRL reads and writes each with final value 0xe000, before stopping at the next read of 0x40021018. PC was 0x488a7c for 2.3/Faceclaw and 0x494964 for 2.4.

Results are outside Git at `Blackwall/simulator/spot-control-storage-01/`. Fifty-four runner tests and three scenario tests passed. Do not extend settings readback into validation of physical power control or normal boot.
