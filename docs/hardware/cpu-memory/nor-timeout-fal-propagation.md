# Propagation of original NOR timeout returns through FAL and FlashDB

bw388. Actual ARM code from stock 2.4, stock 2.3, and Faceclaw shows the path **nonzero NOR error → FAL 0 bytes → FlashDB write wrapper success 0**. Error information is lost at this layer. An actual virtual NOR timeout was not run through this integrated main path, and this does not establish success or recovery of the entire KV setter or physical-device safety. E08 remains incomplete; overall progress is 6/16 = 37.5%.

## Sources and execution scope

The original main SHA, SRAM, and profile from a successful native capture were verified. The original functions were located by following the FlashDB write wrapper's unique instruction signature, the actual database partition pointer, the 64-byte stride lookup table, and the device callback. The connection was not assumed from upstream names or addresses alone.

| Layer | Stock 2.4 | Stock 2.3/Faceclaw |
| --- | --- | --- |
| FlashDB write wrapper | 0x5b42a6 | 0x5a3bde |
| FAL partition write | 0x5bedae | 0x5b4bea |
| device write adapter | 0x57768c | 0x55df64 |
| NOR write | 0x47bde8 | 0x4770d0 |

For each image, the FlashDB wrapper, partition lookup, actual device callback, original NOR write, and original bounded poll were executed in sequence. These are isolated Unicorn M7 calls, not an M55 main reset or execution in the original RTOS context. No broad memory-write observer was used. Input SRAM was read from each native capture, and source files were not modified.

Peripheral and lifecycle ABI leaves are synthetic. SPI transfer, write-enable, controller setup/restore, and synchronization return the specified 0; the status helper returns WIP 0/1, context returns 0/2, and delay/task-delay are stubs that do not advance time. The logging flag is 0, and only error notification API arguments are recorded. The original poll branches, loops, counters, and final return execute as actual ARM code, but actual delays and device responses were not measured. All stub addresses are recorded in the report.

## Observed returns

Seven scenarios per image, 21 in total, ran error and normal modes against the same original code.

| Input | NOR return | adapter return | partition return | FlashDB wrapper return |
| --- | --- | --- | --- | --- |
| Normal 1 byte | 0 | 1 | 1 | 0 |
| Busy timeout, context 0 | 4 | 0 | 0 | 0 |
| Busy timeout, context 2 | 4 | 0 | 0 | 0 |
| Transfer ABI error 7 | 7 | 0 | 0 | 0 |
| Length 0 | 6 | 0 | 0 | 0 |
| Partition out of range | Not called | Not called | -1 | 3 |
| Read-only DB | Not called | Not called | Not called | 3 |

The original poll consumed status 1 exactly 210 times in each of the two timeout paths. The original branch requested delays, but time was stubbed, so 210 iterations are not converted into a physical timeout duration.

In stock 2.4, the NOR 0x47bec6 branch sets r4=4 after poll failure and returns it. Adapter 0x577696 detects the nonzero error, passes notification arguments (operation 2, error 4), and returns 0. The FAL partition returns that value unchanged. FlashDB 0x5b42ba converts only negative values to error 3, so 0 remains success. The normal 1-byte, out-of-range, and read-only controls confirm that the inspector does not invariably see success 0. Original SRAM was identical before and after each call; only the read-only fixture's flag change was specified as initial input.

This risk is not silently fixed by modifying the original firmware. Blackwall's current artifact is a test emulator, not CFW. The original loss of error information must also be observed and reported as-is. The wrapper's 0 must not be treated as “storage succeeded/safe recovery.” The entire original KV setter could still stop at additional reads, error notifications, or other guards, so this is not claimed as final application success.

## Verification evidence

`inspect_nor_error_propagation.py` checked actual layer returns, status counts, notifications, SPI arguments, full PC trace SHA, original SRAM invariance, and stack return for each scenario. The 21-scenario report is byte-exact against the frozen source. All 14 progress-management checks passed. There were no new Renode runs in this work. Two poll failures and a subsequent strict stop on a busy read from an earlier stuck native run are background evidence, not a revalidation of the current integrated path.

```sh
<private-python> tools/inspect_nor_error_propagation.py <simulator> <new-output>
```

The report is private `nor-timeout-propagation-01/report.json`, the frozen report is `nor-timeout-propagation-frozen-01/report.json`, and source/input pins are in `nor-timeout-propagation-research-01/manifest.json`. The existing dataless package was run with a verified local dependency wrapper without overwriting original files.

## Next integrated verification contract

With an explicit virtual fault configuration, leave only the first program incomplete after a normal main hold. Compare the default fault-off case against the existing normal control. Observe the original busy poll and NOR, adapter, partition, and FlashDB return PCs without replacing branches or returns with stubs. Check WIP, incomplete program, unchanged backing, and subsequent strict stop or application return separately. Also connect a new-process read of the same NOR model. If another unsupported boundary such as GAF is reached first, preserve that boundary and do not score it as full recovery.

Erase failure/interruption, stored-version mismatch, and the same integrated failure verification for stock 2.3/Faceclaw remain outstanding. These 21 cases do not replace the full E08 acceptance criteria. The 16 acceptance/status/evidence entries and API 3/6 were unchanged. No physical device, flash, OTA, Astra/subagent, or external publication was involved.
