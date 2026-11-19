# Distinguishing the UART0 interrupt mask from DMA start

`bw-0224`: The pinned HAL, SVD, Apollo510 header, and three inputs from existing original ARM execution were compared. All 53 checks in private `simulator/uart0-interrupt-mask-contract-01/report.json` passed. Reproduction tool: `tools/inspect_uart0_interrupt_mask.py`.

Stock 2.4 at `0x5ae4a4` and stock 2.3/Faceclaw at `0x5add98` store `0x1fd0` in UART0 IER (`0x40039038`). The caller passes the constant mask directly; the existing IER is read, ORed, and stored. The UART0 mask before that stop is 0, and transmit/receive DMA is not implemented.

The mask enables RX, receive timeout, framing/parity/break/overrun errors, and DMA complete/error interrupts. It excludes TX/TX complete. DMA interrupt mask `0x1800` does not start DMA. Separate DCR (`+0x48`) has RXDMAE bit 0 and TXDMAE bit 1; SVD reset is 0.

The next model extension permits storing the upper two mask bits only under UART0, interrupt-enabled, explicit source-reset DMA-idle profile. Keeping DMA raw state at 0 is a simulation assumption that DMA has not been started since reset, not a measurement of physical device DMA idle. DMA enable, RX data, and completion/error generation are unsupported; unknown accesses continue to stop. Other ports and default profiles retain existing restrictions.

This does not mean successful full boot, display, BLE reception, or DMA transfer. Existing execution conditions, including missing external font diagnosis and simulated HCPA responses, are retained; original code and branches are not changed.
