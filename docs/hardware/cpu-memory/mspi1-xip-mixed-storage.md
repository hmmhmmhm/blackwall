# XIP mixed-mode storage model

Task bw-0170. Overall completion remains 13/29 (44.8%). This step stores transfer format settings; it does not implement NOR data, SPI lane behavior, or XIP execution.

## Source contract and implementation

The next DEV0XIP write in the three existing original images, 205ED→200ED, changes only XIPMIXED[11:8] from 5→0. The public SVD defines 5=D4 and 0=NORMAL. The original firmware also clears only this field with ldr→bics F00→str. The HAL device configure path was confirmed to set NORMAL, D4, and other values in the same field. NORMAL is a format that follows DEVCFG settings; it is not interpreted as a particular physical clock or DDR multiplier.

The 24 checks in `inspect_mspi1_xip_mixed.py` compare fixed source and original bytes, storage logs and markers, and the read-modify-write operation. Documented values are 0, 1, 3, 5, 7, 9, and 11. No behavior is inferred for the remaining mixed values.

`xipMixedStorage`, defaulting to false, was added to `BlackwallMspi1ConfigStorage`. With XIP active, it stores only the selected field while preserving the existing enable, readonly 32 MiB AXI configuration, and power/clock conditions. When both turnaround and mixed options are enabled, combined changes to both fields are allowed, with each storage count recorded separately. `CanChangeTiming` was renamed `CanChangeConfiguration` to match its scope, and callers in the same file were updated.

Simultaneous initial enable and field change, other format fields, reserved modes, PIO busy, and clock off are rejected. Unknown XIP bytes remain strict. Storing values for seven modes whose data is unsupported is separate from actually transferring flash data in those modes.

## Execution evidence

- unit01: red stage where platform loading failed because the constructor option was not implemented.
- `mspi1-xip-mixed-unit-02`: 63 checks passed. It added documented 7 values, rejection of 9 reserved values, D4→NORMAL, combined fields, clock/PIO guards, reset, and unknown data blocking to the existing 39 turnaround checks.
- `mspi1-xip-mixed-main-01`: four conditions comprising original stock 2.4, stock 2.3, Faceclaw, and an option-false control. Original main/vector and the existing execution policy were retained. The 2.3/CFW model and runtime have identical conditions apart from main length.
- All three originals recorded one mixed store, three turnaround stores, value 200ED, 54 config reads, and 69 writes. The next operation writes 30441 to MSPI CTRL 40061000, at PC stock 2.4=4E8A46 and stock 2.3/Faceclaw=4DB672.
- At the same point INSTR=9F, DEV0CFG=03010861, and CTRL1=0. CTRL 30441 is a request containing length 3, RX, SENDI, and turnaround. The current PIO model rejected it and generated no ID or FIFO data.
- The option-false control retained the existing DEV0XIP 200ED write / PC 4E683A boundary. XIP aperture accesses were 0.

Next, investigate the device contract for command 9F, the PIO RX FIFO and read completion/error handling, and the basis for an explicit device profile. Do not treat the chip actually installed in the G2 as confirmed or select an arbitrary ID to pass firmware checks.

The existing chip revision, power-ready, ADC, and virtual NOR reset timing assumptions remain. No physical glasses connection, flashing, or persistent write was performed. Full ROM/boot startup, BLE, NOR data, integrated display, and physical device recovery remain incomplete.

`mspi1-xip-mixed-regressions-01` reran the previous 39 turnaround and 26 PIO checks against the current combined source; all 65 passed. The 62 checks in `mspi1-xip-mixed-verification-01` compared current source, unit driver, board, original bytes, derived hashes, markers, next guard, INSTR 9F/RX3 settings, zero aperture accesses, default control, identical 2.3/CFW conditions, and regressions.

The inherited parent-model review raised no further significant issues. Stored settings were distinguished from actual data transfer, and 9F was reported only as an ID read attempt. Astra, another model family, and a full transcript audit were not used.
