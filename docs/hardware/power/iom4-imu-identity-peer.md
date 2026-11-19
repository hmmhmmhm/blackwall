# IOM4 Virtual IMU Identity and Natural Main Execution

bw-0321. Based on the [original transfer contract](iom4-polling-imu-contract.md), a limited I²C peer is connected at IOM4 address `0x69`. Firmware instructions, branches, and returns are not patched and functions are not forced to return. This model does not reproduce a physical IMU, sensor samples, or reset.

## Model scope

The `icm45608-whoami-only` profile in `tools/renode-imu-identity.cs` supports only one-byte register-select `72` and a subsequent one-byte read. Response `81` is an explicit fixture based on pinned TDK source and the original comparison instruction, not a value measured from actual glasses. Other bytes may be selected as diagnostic fixtures but are not confused with natural-main verification of that path.

The existing source-derived I²C backend puts the peer's one-byte response in one FIFO word. Original HAL sees FIFO1SIZ=4, pops the word, and stores one byte in the caller buffer. The peer does not fabricate four bytes or bypass HAL FIFO checks. IOM CQ/DMA models are unchanged.

Invalid registers, data writes, read lengths, reads before selection, and reuse of consumed responses are rejected. Unsupported accesses record only diagnostic attempts and do not advance peer supported state, returned data, or completion history. Since the inherited controller may advance some command/FIFO state before calling the peer, this is not described as side-effect-free blocking of the whole controller. Controller reset and external peer reset are independent.

## Verification method

`tools/verify_iom4_imu.py` checks actual Renode IOM controller, FIFO, IRQ clear, and peer reception/lifetime. The initial missing-type failure was preserved before implementation. Twenty-one checks passed. These are synthetic register drives, separate from original main boot tests.

The frozen copy also passed 21 checks with all report keys/values matching. Initial raw byte identity failed due to IronPython JSON key order. Both original files and failure records were preserved and compared as fully parsed data and canonical JSON; raw files are not reported byte-identical. The 459 Python sources in tools are byte-identical to the frozen copy and passed syntax checks, not functional tests of 459 tools.

`tools/prepare_iom4_imu_candidate.py` reuses bw319 pinned original-reset inputs and component hashes and bw320 source contract. Nine existing models are unchanged; only the peer is added. Diagnostic variables and IOM4 peer-attached indication reflect actual connection; control applies no board/runtime changes. Existing IOM7 indication is preserved.

The first native attempt failed post-exit diagnostic collection when Python directly queried inherited `Children`'s explicit interface implementation. It is not used as a successful capture. A runtime edit anchor inconsistent with existing peer-attached representation was subsequently rejected before execution. Failure files were preserved and diagnostics corrected to reference the actual board peer.

## Current results

Original stock 2.4 main completed `72` selection → one-byte `81` reception and strictly stopped at next register-select `2d`. The initial provisional bounded-capture contract failed because it differed from the actual strict boundary; the original report was preserved. A separate saved audit changing only that capture plan's semantic contract passed.

`inv_imu_soft_reset` in pinned TDK commit `646f55a6ec119b59d9ebce47af660842b53e5506` first preserves `INTF_CONFIG1_OVRD`; the register map defines its address as `2d`. This correspondence explains the next investigation point. No arbitrary success value is supplied for initial `2d` or reset-complete state. The actual sensor reset write was not reached.

Stock 2.3 and Faceclaw also reached the same identity transfer and next `2d` query. Actual HAL stack descriptors in three images are address 69, write 1, transmitted byte 2d. Controller command count 3 includes two successful WRITE/READ commands and the next WRITE attempt rejected by the peer. This is distinct from peer success select 1, read 1, one returned byte, and finish 2. CQ pairs processed: 0.

| Input | Next strict PC | Transfer | Next unsupported request |
| --- | --- | --- | --- |
| Stock 2.4 | `58236c` | register 72 / response 81 | register-select 2d |
| Stock 2.3 | `57b014` | register 72 / response 81 | register-select 2d |
| Faceclaw | `57b014` | register 72 / response 81 | register-select 2d |

Peer-off stock 2.4 exactly matched previous CPU state and all observed events. Each capture's semantic contract and file pins were checked in four separate saved audits. The first diagnostic-failure native run and pre-execution anchor rejection were preserved and not combined with four verified main runs.

Full boot, app loop, nonzero screen, and successful actual touch input are not established by this result. Overall goals of web installation, recovery boot, Faceclaw CFW, and integrated simulator remain. Product completion remains 13/29=44.8%, scope v2. Final frozen/verification assets are private `simulator/iom4-imu-verification-01/manifest.json`.

## Next sequence

Compare the complete `2d` interface configuration preservation → drive configuration preservation → soft reset → status check/restore with the original function and pinned TDK source. Determine whether reset, power lifecycle, virtual time, and errors can be modeled together before expanding. Then continue connecting natural-main nonzero draw and framebuffer viewer. No actual device connection, installation, or permanent write is performed.
