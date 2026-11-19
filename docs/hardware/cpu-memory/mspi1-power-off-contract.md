# MSPI1 Retention Power-Off Boundary

Subsequent implementation and execution results are in the [controller power-off model](mspi1-power-off-model.md). Statements below about unimplemented behavior and the current endpoint describe the time of the contract investigation.

## Conclusion at that point

After retention save, original main requests `PWRCTRL.DEVPWREN(0x40021004) = 0x400`: **clear MSPI1 bit 15 while retaining UART1 bit 10**. Do not interpret it as a UART initialization request. At that point the MSPI1 power owner had neither an off response nor a shutdown callback configured, so it deliberately rejected the request. Do not inject arbitrary success values or branches to resolve this.

`tools/inspect_mspi1_power_off_contract.py` compared pinned SVD/header and HAL SHA with three original mains and prior native execution records. The final result is 57 checks in `simulator/mspi1-power-off-contract-03/report.json` outside Git. These are source/record contract checks, not counts of new native executions or physical power verification. Initial `contract-01` failed because it did not handle SVD use of bitRange instead of bitOffset/bitWidth and was preserved. `contract-02` had 51 checks; `03` added six original instruction checks for return-value handling.

## Evidence of original behavior

| Item | Stock 2.4.0.24 | Stock 2.3.0.24 / Faceclaw 38 |
| --- | --- | --- |
| Peripheral-disable function entry | `0x494e96` | `0x488fae` |
| Current strict store PC | `0x494f3e` | `0x489056` |
| Retention call to disable | `0x4e935c` | `0x4dbf88` |

Addresses are verified in each original main; do not assume the entire HAL shifted by a single offset. The peripheral-function difference is `0xbee8`, MSPI HAL difference `0xd3d4`.

Current register/stack context supplies enable address `0x40021004`, enable mask `0x8000`, status address `0x40021008`, and status mask `0x8000`. Original instructions read enable, clear the mask with `BICS`, and store it. Therefore the previous value, combining request `0x400` and the cleared mask, is `0x8400` under the current mock owner combination. Do not generalize this as actual hardware reset state.

Pinned HAL source rejects sleep when HP/CQ is pending and saves retention registers and disables interrupts. If XIP enable is set, it delays to flush pending memory transactions, then disables peripheral power, disables the clock gate, and releases the clock. In the current capture PIO is idle, recovery false, RX FIFO empty, and CQ/DMA disabled. **DEV0XIP is `0xed` with bit 0 set, and the XIP guard is enabled.** There is no backing data, however, and aperture accesses are zero. It would be wrong to say XIP is off.

## Limit identified in failure handling

The peripheral-disable function itself polls status and returns a result, but its MSPI retention caller does not check that return. Across all three originals, instructions after `BL peripheral_disable` prepare argument registers, overwrite `r0` with the module number, and call the clock helper. One cannot claim that failed power-off leads to safe fallback. **Actual execution of this failure path had not yet been verified.** A subsequent stuck-on model must observe clock gating and the return path.

## Boundary for the follow-up model

At this point `BlackwallMspi1ConfigStorage.Reset()` also calls PIO Reset, which initializes external NOR WEL, four-byte mode, and recovery state. Using it unchanged for MCU-internal MSPI power-off mixes in an unverified assumption that the external NOR was reset too.

The next model must separate internal controller initialization from external NOR state. Whether the MSPI1 power bit actually cuts external NOR supply is unknown. In an explicit mock condition where external power is retained, preserve NOR state and distinguish it from full simulator reset. Allow shutdown only in a known idle state; do not treat busy/RX pending/recovery/CQ or DMA activity and unimplemented XIP accesses as success. Retain blocking for default unknown.

Test successful off and stuck-on responses as separate opt-in conditions. Preserve other power owners including UART1, and separately verify internal register and IRQ initialization and NOR retention. Mark actual register-loss scope, external supply, and physical rails as source-supported or hypotheses rather than physical verification.

Runtime models and the original execution endpoint were not changed in this work. Full boot and integrated display remained incomplete; product criteria stayed 13/29, 44.8%. BLE, glasses connection, RAM payload, OTA, flash, and MRAM writes were not executed.
