# Original IMU soft-reset contract and remaining timing model

bw-0322. Natural main in bw321 stopped at register 2d lookup after register 72 identification response 81. This work establishes the source contract for the next reset behavior unit. No new native main execution or peripheral model change occurred.

## Sequence required by the original function

Actual caller → advanced reset → soft reset calls were linked across three originals. Soft-reset entry is stock 2.4 `553616`, stock 2.3/Faceclaw `51f7be`.

1. Preserve one byte of `2d` INTF_CONFIG1_OVRD on the stack.
2. Preserve one byte of `32` DRIVE_CONFIG0 on the stack.
3. Write 02 to `7f` REG_MISC2. Reset is bit 1.
4. Request 1,000 µs through the sleep callback.
5. Restore preserved 32, then 2d.
6. Read `19` INT1_STATUS0 and check bit 7 RESET_DONE.

Register names and masks were compared with TDK ICM45608 source pinned by Git commit/blob in bw320. The [pinned driver](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_driver.c) shares the save/reset/sleep/restore concept, but the latest driver's full internal-state initialization, endianness handling, and post-reset hook are not all present in this G2 soft-reset function. The full upstream ABI and function are not assumed identical.

The sleep argument is a request confirmed in original instructions, not measured elapsed time. The callback's actual clock/ROM path has not been verified. The main capture callback is nonzero; it was not changed to NULL to skip waiting.

## Independent ARM fragment verification

`tools/inspect_imu_reset.py` validates original main, full SRAM, and saved-audit file pins per capture, then runs. It statically checks the full reset function's call order and key arguments, and executes these fragments in separate CPU/stack fixtures:

- 256 status bytes × three accumulated-status fixtures: without RESET_DONE return ffffffff; with it return accumulated status OR final read status. An error status is not changed to success 0 just because reset-done matches.
- 256 saved bytes × two restore-preparation fragments: original instructions prepare the saved stack byte unchanged as the one-byte write argument for 32/2d. Execution stops before the transport callee; actual restore transfer is not claimed.

There are 1,280 fragments per original, 3,840 across three. This independently verifies status judgment and argument construction, not connected execution from reset start to finish. It does not establish arbitrary register defaults, actual clock delay, reset completion time, read-to-clear lifetime, or electrical bus behavior. All byte combinations are synthetic and not necessarily physically valid bit combinations. Production firmware instructions/branches and device firmware were unchanged.

## Experiments not adopted

Original disassembly and experiment failures are preserved in private `imu-reset-research-01`. The native snapshot's I²C mutex was already locked, so a new upper-function call competed with the existing request and waited. This is neither reset failure nor the normal path.

A control resuming from the actual HAL frame consumed the 2d read but also needed GPIO configuration storage and IOM context-save read ranges. The temporary fixture lacked complete controller state such as FIFO threshold, clock, CQ, and DMA trigger. Actual capture has DMA trigger 2 and nonzero CQ address/pause; context must not be constructed with arbitrary zeros. This experiment is not evidence of a valid reset prefix, full reset, or existing-model compatibility. Unsupported MMIO was not bulk-filled with 0 to proceed.

## Documentation and implementation boundary

The [official TDK product page](https://www.invensense.tdk.com/en-us/products/inertial-sensors/icm-45608-ict-15318) points to DS-000595 ICM-45608 Datasheet v1.1. Public driver headers obtained so far do not establish actual 2d/32 power-on defaults and all reset side effects. Do not import datasheet values from another ICM model.

The next implementation must retain the existing I²C backend and handle explicit initial configuration fixtures, virtual-time reset pending/done, configuration loss/restoration, and status consumption as one lifecycle. Preserve the WHOAMI-only default profile and enable this separately. Report integrated reset execution only after checking write order, requested time, restore values, and incomplete/error controls on actual original M55. Distinguish source-backed requirements from physical confirmation.

Overall 13/29=44.8%, scope v2. Web installation, Faceclaw CFW, recovery boot, integrated simulator, and screen remain in progress. No new boot, integrated UI, or physical verification success.
