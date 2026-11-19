# IMU indirect address/data and original endianness cache

bw-0324. The `7c a2 67` request after [virtual reset](imu-timed-reset-peer.md) was connected to an internal register lookup. The new profile activates only when an explicit `sregControl` byte is specified with the existing reset profile. Default -1 retains the existing blocked boundary. It is not a physical value or full chip model.

## Original protocol

The same flow was confirmed in three originals and pinned TDK source:

1. Upper `read_reg(a267,1)` selects the indirect read helper.
2. After requesting 4 µs sleep from the callback, write `7c a2 67`. Internal address order is high → low.
3. Request another 4 µs, select `7e`, and read one byte.
4. On success, the upper getter stores byte bit 1 at device context+11. On error, it preserves the existing cache.

`IREG_ADDR_15_8=7c`, `IREG_ADDR_7_0=7d`, `IREG_DATA=7e`, and `SREG_CTRL=a267` were compared with the TDK register map pinned by commit/blob in bw320. This path does not poll the IMU's IREG_DONE; it is distinct from existing IOM controller completion polling. No unused ready-register value is fabricated.

`tools/inspect_imu_ireg.py` validates pinned originals, audit, and full SRAM and checks helper instructions and callback arguments. Across 2,304 independent ARM cache fragments (256 bytes × three statuses × three originals), it checked bit 1 storage, preservation on error, returns, and stack restoration. This is not execution of the entire transport. Actual main connection was checked separately.

## Model scope

The optional IREG timer in `tools/renode-imu-identity.cs` supplies one byte at address a267 only. It can be requested only after reset configuration restoration; data become ready after a declared virtual 4 µs following address setup. This number is not verified as actual or worst-case physical chip access time.

Overlapping addresses, other addresses, data writes, early reads, reads of different length, and the next byte after consumption are rejected. Hardware auto-increment after consumption and other register values are not assumed. Diagnostic `IregAddress` is the last supported address, not a full internal chip pointer model. External IOM controller reset does not cancel the timer; peer reset does. Actual power-rail lifetime is unknown.

`tools/verify_imu_ireg.py` runs 63 checks including 44 existing ones. The red for an unimplemented new constructor feature was preserved. It checked not-ready at 3 µs, subsequent ready, data preservation after wrong length, single consumption, timer cancellation, and independence from controller reset. The new configuration does not automatically extend the default reset/WHOAMI profile.

## Actual original main results

| Input | SREG fixture | Actual cache byte | Next unsupported request |
| --- | --- | --- | --- |
| Stock 2.4 | 00 | 0 | register 24 select |
| Stock 2.3 | 00 | 0 | register 24 select |
| Faceclaw | 00 | 0 | register 24 select |
| Stock 2.4 value control | 02 | 1 | register 24 select |

Execution from original main reset confirmed one each of IREG request, timed completion, and data read, five total received bytes, and 14 successful I²C finishes. The original ARM getter stores the cache; the model does not write SRAM. Actual saved context address and getter store instruction, prior pinned inputs, and file pins of four captures were checked together. This does not extend to verification of sensor sample 16/32-bit conversion or physical byte order.

The indirect-disabled control exactly matched bw323 reset-only full CPU state and observed events. There are five valid native runs and five saved audits. The first provisional boundary contract failure was retained and passed a separate audit changing only its own capture plan's semantic contract. Original firmware instructions/branches/returns and existing observers were unchanged.

All 63 frozen-model unit checks passed, with all report keys/values matching the original run. All 2,304 frozen-source fragments passed; report and inspector artifacts were byte-identical. 465 Python sources were byte-identical to frozen source and passed syntax checks. This is not functional testing of all 465 tools. Related source, failures, runs, audits, and native cache checks are preserved in private `simulator/imu-ireg-verification-01/manifest.json`. The new model changes one IMU peer and retains nine existing peripheral models.

## Next sequence and completion scope

The next direct register 24 is FSYNC_CONFIG0 in the pinned map. Analyze the next advanced initialization behaviors such as FSYNC/FIFO tags in original and SDK, and extend the full post-reset path. Do not pass by inserting an initial value of 0. Then continue nonzero main draw and framebuffer/576×288 viewer integration.

Overall 13/29=44.8%, scope v2. The overall goals remain web installation, Faceclaw CFW, recovery boot, integrated simulator, and screen. Full boot, app loop, integrated UI, and sensor samples remain incomplete; no physical access, installation, or persistent writes.
