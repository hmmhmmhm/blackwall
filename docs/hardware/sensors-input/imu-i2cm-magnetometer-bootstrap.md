# I²C master and virtual magnetometer initialization

bw-0330. After [auxiliary interface configuration](imu-auxiliary-bootstrap.md), original M55 main in stock 2.4, 2.3, and Faceclaw completed virtual magnetometer reset, MRM, ID, and status queries. All three images were also confirmed to store ID byte 45 and ready byte 1 in SRAM. This is not a physical sensor reading from the glasses.

## Model and transport contract

Optional `magnetometerFixtureHex` declares five initial bytes for master control, MAG ID, sequencer, mode, and status. Default experimental value `a045000000` is a test profile, not physical register defaults or physical chip identification.

`BlackwallImuI2cMaster` supports these commands and completion flow:

| IMU internal register | Role | Scope supported here |
| --- | --- | --- |
| `a20f`, `a20e` | slave 1e, read address | channel 0 |
| `a233..a238` | write buffer | storage and post-init configuration in verified range |
| `a206` | single command | read1=`91`, write2=`82` |
| `a216` | go, speed | original RMW, read lease, virtual timer start |
| `19/1a` | completion polling | consume bit 13 latch once after completion |
| `a218` | busy/done/error | declared status matching original error mask `3d` |
| `a21b` | read result | consume completed read1 result once |

Execution is limited to the original's single-command, channel-0 read1/write2. This is not a model of all SDK multiple slaves, four-command combinations, long bursts, or measured magnetic-field generation. MAG covers only this initialization path through ID01, sequencer7c, mode04/05, status06, and protected register7f. Unprotected reset and unsupported registers/commands are rejected.

Results and polling flag become ready after the completion timer. Virtual time 1,000 µs is not measured physical transfer time. Physical clock, I²C electrical signals, GPIO/NVIC IRQ, and MRM magnetic-field computation were not verified. The control byte retains declared stored state and does not guarantee actual automatic clearing of the go bit.

Indirect write sends `7c + 2-byte address + first data`, continuing with `7e + data`. Cursor handling was connected after comparing existing SDK transport source with first native stop `7e1e`. Tests prevent continuation being misinterpreted as a new slave setting and losing the read address. The first 13-transaction capture and missing-stream red were preserved.

## Actual original M55 results

All three normal images performed these 13 transactions:

`w7f=ca → r7c=00 → w7c=80 → w7f=00 → r05=00 → r04=00 → w04=03 → r05=03 → r04=03 → w04=00 → r05=00 → r01=45 → r06=00`

This is not an initialization sequence executed by the model in place of the CPU. Original firmware built the command buffer, wrote go, and repolled completion; the model supplied declared virtual sensor responses. Thirteen completions, read 8/write 5, one reset, one ID read, 39 indirect reads, 319 I²C finishes, and 143 received bytes were confirmed. Initial 0/0 and resulting 45/1 for ID/ready stored by original code were compared by following actual store locations in raw SRAM.

Original code also disabled completion interrupt configuration again and wrote the post-init profile/buffer. The next unsupported request is external sensor ODR configuration `DMP_EXT_SEN_ODR_CFG(27)` lookup. ODR configuration itself has not yet executed. Firmware instructions, branches, and returns were not modified and no new CPU hook added.

## Error controls and limits

| Condition | Observed result | Not guaranteed |
| --- | --- | --- |
| Normal ID45 | 13 transactions, ID/ready 45/1, completion interrupt disabled, next register 27 lookup | Physical normal behavior, full boot |
| ID44 | 12 transactions, ID/ready 0/0, completion interrupt setting remains, upper routine advances to register 27 lookup | Whole-system fail-stop on compatibility error |
| Missing completion | One start, zero completions, six polls, no ID received, ready 0; host ends collection | Permanent whole-system hang or watchdog recovery |

The ID44 control confirmed actual result reception with 36 indirect reads. Rejection by the ID gate and safe stopping of upper initialization are distinct conditions. The upper caller's final error return and subsequent fallback require further examination.

The original completion polling loop and pinned SDK wrapper check done/status without their own software timeout. Do not extend a short nonresponse observation into evidence of indefinite execution. Future Blackwall compatibility fallback and timeout design must address this path. No firmware timeout patch was added here.

## Observation and verification

Normal execution's 4,192 events exceed the previous 4,096 capacity, so retention was raised to 16,384. Only the observer constructor's allowed maximum changed to 32,768; existing hooks were preserved. A buffer-only control exactly matched the original in full CPU and all observation fields except capacity. The default 4,096 control with master off also exactly matched all CPU/observations. This does not generalize to a guarantee of no effect from new hooks.

`inspect_imu_i2cm.py` checks original encoder, go RMW, and error consumption across three images in 2,334 scenarios. Encoder tests replace the write-reg callee with an explicit ABI stub. That standalone test is not natural main; native runs above execute actual firmware transport functions.

All report values matched between 229 unit and 229 frozen checks; 2,334 source and 2,334 frozen cases passed. Source report/inspector artifacts were byte-identical. 477 Python sources matched frozen source and passed syntax checks; this is not functional testing of all tools. Nine existing peripheral models were unchanged; two components, IMU peer and observer, changed.

Seven current-model native runs and seven saved audits, plus one preliminary native before stream connection, are preserved. Error/observer/cursor reds, provisional contract failure, and metadata before register 27 naming correction remain. Final evidence is private `simulator/imu-i2cm-verification-01/manifest.json`. Four historical planner paths match except for current IMU source SHA; only the master path explicitly records observer change. The shared unit harness observer-selection option does not change default behavior.

Next connect external sensor and accel/gyro ODR and FIFO configuration as behavioral units, then proceed to nonzero main draw and framebuffer/576×288 viewer. Overall 13/29=44.8%, scope v2 remain. No physical connection, installation, or persistent writes. Full boot/UI remains incomplete.
