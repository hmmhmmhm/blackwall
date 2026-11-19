# Original FIFO setter and shared configuration lifetime

bw474 is an **explicit M55 API diagnosis** in which the stock 2.4.0.24 original ARM setter configures raw32 FIFO through actual IOM4 transfers, then the original upper consumer/parser reads ten packets. The host device frame-size seed was removed. This is not completed natural main sensor initialization, GPIO IRQ connection, or physical verification. E12 remains partial and overall acceptance remains 10/16=62.5%.

## Changed conditions

In [bw473](imu-fifo32-parser-and-transport.md), the host set device frame size to 32 before consumption. Here, at pinned cold main getter breakpoint `0x5542c6`, frame size 0 and a free IOM4 mutex are confirmed, then a separate ITCM caller invokes original setter `0x553196`. Inputs are the raw32/ES0·ES1, mode 2/depth 7, WM10, compression 0 configuration observed in [bw472](imu-fifo-guest-configuration-contract.md)'s actual enable branch.

Only after the setter returns normally does the host insert ten raw32 test packets into the peer, and a second caller invokes original upper function `0x4c38b0`. Execution passes original FIFO API→actual IOM→original parser/callback/ARM result decoder and stops at `0x4c3ad0` immediately after parser return. **Return of the entire upper function was not confirmed.** Sample ES bytes are declared test inputs, not normal GAF computation results.

Host PC changes are explicit conditions for running these diagnostic callers. Do not describe them as forcing passage through natural main branches. The host does not write frame-size/endian/gate/TCB/IRQ mask. The caller only reads PRIMASK/BASEPRI/CONTROL/IPSR and runs on the existing Sensor Thread/PSP.

## Supported model scope

- `renode-imu-fifo-configuration.cs`: FIFO_CONFIG0..4 (`0x1d..0x22`), decimation (`0x28`), timestamp field (`0xa258`). Initial FIFO_CONFIG0=0, limited to supported bypass 0/7 and raw32 stop-on-full 0x87. It reflects reset value 0 in ICM-45608 DS-000595 rev1.1 §16.28. Enqueue is rejected before raw32 ES0 size 9/ES1·accel·gyro/uncompressed configuration.
- `0x20` is solely owned by the existing power/flush component. No separate bank truth is created; only comparator bit 3 is modified under read-lease/flush-completion conditions.
- `0xa258` shares its value with the existing ODR owner. RMW of FIFO timestamp low 2 bits and ODR low-power bit 4 is separated; reserved-bit changes are rejected. Value `0xd8` produced by existing ODR in native is preserved. The standalone fixture's `0x60` without ODR does not overwrite the native initial value.
- Internal registers use existing timed IREG transfers. Existing ODR dispatch remains before bank activation. No new ready shortcut exists. Only standalone unit tests declare `initialIregReady=true`.
- IOM 4-byte TX chunks are collected to a complete payload, validated, and atomically applied to the bank. Incomplete write Finish and invalid complete writes are rejected. WM low/high order and uint16 values are preserved.
- WM/comparator/INT1 mask derive from actual shared configuration. Threshold IRQ remains a logical signal, not yet connected to GPIO38.
- Reconfiguration is rejected with a FIFO read lease, remaining packets, or pending threshold. Unsupported live reconfiguration, compression, and other frame modes are not arbitrarily made successful.

Full transport reset initialization of configuration/queue was tested. Reentry of a soft-reset command during execution and recovery of pending IREG during partial raw reset are outside this completion scope. The existing identity's first-reset-only condition remains and is not expanded into E06 completion.

## Original execution observations

| Item | Result |
| --- | --- |
| Original main | stock 2.4.0.24, SHA256 `df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a` |
| Setter | R0=0, returned to caller, SP/current TCB preserved |
| Device configuration | frame 0→32, endian 0, FIFO used 1, compression 0 |
| Peer configuration | Ready, WM10, bank read 2/write 7, timed indirect read 1/write 1, shared FIFO 0x2d/timestamp 0xd8 |
| Consumption | 10×32=320 bytes, callback/decoder 10 times each, ring header `[0x10203040,10,10]` |
| Stop boundary | parser R0=0, `0x4c3ad0`, mutex returned, gate 0 |
| Execution mode | PRIMASK0/BASEPRI0/CONTROL6/IPSR0, original Sensor Thread/PSP |
| Errors | guard/memory-policy/CFSR/HFSR all 0 |

`completed=6` is the adapter's cumulative logical read-lease completion count: two configuration reads + four status/count/count/data reads, not the total physical I²C CMD count. The resulting 2252-byte ring is compared with independent formulas using original raw axis, bias, and period inputs.

## Verification and reproduction

Run standalone configuration verification with `tools/verify_imu_fifo_configuration.py <private-simulator> <new-output>`. Its 32 checks use actual Renode IOM and time advancement, including 3 µs not-ready/5 µs ready, atomic writes, rejection of partial Finish, shared fields, WM257, sample gating, and reset. Existing raw32 70/raw16 228/transport 176/ODR 1278/threshold 27 checks are retained separately.

The final native pair and audit are preserved outside Git in `simulator/imu-fifo-registers-research-01/`. The audit uses only `frozen/` inputs, C#, runner, and baseline, not retrospective references to current ROOT files or the latest candidate builder. The native pair is `imu-fifo-registers-setter-m55-05` and `imu-fifo-registers-setter-no-watch-02`. Initial SRAM, post-setter SRAM, and final SRAM/WORK are compared with observation on/off. All 109 saved-input audit checks passed; 21 containers from this work were confirmed removed and absent. Asset list and SHA256 are recorded in `simulator/imu-fifo-registers-manifest.json`.

The entire previous board identity was not replaced with a newer file to make the cold prefix. Pinned initialization Fsync/reset/readiness guards were retained, incorporating only required extension dispatch and shared Power/ODR ownership. Remaining GAF code was preserved identical to the pinned baseline and checked by full model reconstruction.

## Failures and limitations

- Initial missing-class, TX chunking/incomplete Finish rejection, missing controller reset, and reset value 7→0 check failures were preserved. Failures are not counted as successes.
- The initial native recipe was rejected before the VM due to frozen identity mismatch. The next attempt intercepted `0xa258` before bank activation, breaking existing ODR order. Activation conditions and single ownership were corrected.
- One harness left a memset address instead of memcpy in actual setup. That run was excluded rather than treating prefix arrival as setter success. The address is obtained from the original memcpy's unique ROM signature and actual `setter.Seed(15, …)` AST is checked. If replacement is missing, an undefined token fails before CPU execution. Wrong address, absent replacement, duplicate, and missing input are also rejected by guards.
- The earlier native success pair with reset value 7 is preserved as historical profile evidence. The final reset-0 source is evidenced by the separate new pair.
- ODR observer capacity error and missing CLI argument are distinguished as test-preparation errors.

The next integration target is **threshold derived from actual configuration→GPIO38→original input consumption**. Normal GAF/EDMP computation blocking natural initialization is still unsupported and is not bypassed by manipulating gate/ready. This feature provides a diagnostic basis for original configuration and FIFO consumption, not evidence of physical glasses boot or six seconds of normal operation.
