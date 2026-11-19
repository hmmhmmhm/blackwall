# MSPI1 Clear-All Interrupt Command

Task bw-0166. The overall goal at the time was web-installable Faceclaw CFW, recovery boot, a stock-based simulator, development tools, and integrated display where possible. Product acceptance remained 13/29 (44.8%).

## Source contract and implementation

The next original execution stop after bw165 was a write of `FFFFFFFF` to MSPI1 INTCLR `0x40061208`. `am_hal_mspi.h` in pinned Ambiq HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` defines `AM_HAL_MSPI_INT_ALL=0xFFFFFFFF`, and its `.c` file has several paths that actually write it to INTCLR. `am_hal_mspi_interrupt_clear` also writes its mask argument and reads INTSTAT. Implemented bits in the public Apollo510 SVD/header remain 0–13 (`3FFF`).

Added an `allowAllClear` option, default false, to `BlackwallMspi1Interrupts`. When selected, **only an exact FFFFFFFF write to INTCLR** is interpreted as W1C for the 14 currently implemented bits. This is not a general reserved-bit write-ignore model. FFFFFFFF on INTEN/INTSET, other reserved-bit combinations, direct INTSTAT writes, alias reads, and unsupported widths remain strict. The power condition also remains. ClearAllWrites counts accepted commands and resets to 0 on Reset. Actual physical hardware response to reserved bits was not measured.

`inspect_mspi1_clear_all_contract.py` checked HAL SHA/Git blob, the macro and usage paths, metadata mask, and the store attempts of all three originals in 20 checks. Initial contract01 failed because it incorrectly assumed readback immediately after the original store. The actual instruction sequence contains adds and another store, so 02 checks only the store attempt. Do not equate readback in the HAL function with subsequent behavior at this original call site.

## Execution evidence

- `mspi1-clear-all-unit-01`: red phase; platform loading failed because the new constructor option did not yet exist.
- `mspi1-clear-all-unit-02`: 82 passed. Checked the existing 73 IRQ cases plus clear-all, repeated clear, rejection of EN/SET FFFFFFFF and other reserved clears, and reset. These were synthetic software events, not evidence of physical transfers or the original ISR.
- `mspi1-clear-all-main-01`: original ARM stock 2.4, 2.3, and Faceclaw plus an option-false control, four conditions in total. Original main bytes, vectors, and existing CPU/memory policies were preserved; 2.3/CFW models and runtime used the same conditions.
- The three originals each cleared all once, with enable/status 0, IRQ low, and three IRQ reads/four writes. The next unimplemented request was a `C1` write to MSPI1 CTRL `0x40061000`: stock 2.4 PC=`4E8A46`, stock 2.3/Faceclaw PC=`4DB672`.
- The option-false control stopped at the existing INTCLR FFFFFFFF boundary, PC `4E8A3E`, as before.
- `mspi1-clear-all-verification-02`: 56 saved-evidence audit checks compared current source, unit driver, board, original bytes, asset hashes, markers, next guard, control, and equal 2.3/CFW conditions.

## Next boundary and limits

CTRL C1 contains START (bit 0), SENDI (bit 6), and TXRX (bit 7), with a transfer byte count of 0. The public SVD describes it as the register that starts a PIO device command. Saved config markers show INSTR=`66`, DEV0CFG=`01410061`, and ADDR=`0` for all three inputs. The opcode's meaning is not yet established. The next task is to compare these values and the original caller to identify the target NOR command and model transfer start, completion, and failure semantics. No fake success or NOR bytes were supplied for an unimplemented transfer.

Existing synthetic chip revision, power-ready, ADC, clock, and other assumptions remain. This is original execution from main reset, not full boot including ROM/bootloader. Actual BLE/MSPI/NOR transfers, integrated display, and physical installation/recovery remain unverified. This work involved no glasses connection or persistent writes.

A review inheriting the parent model found no additional material issues. It distinguished the HAL contract from physical reserved-bit behavior, the original store from HAL readback, and PIO start from transfer completion. No Astra, other model-family review, or full transcript audit was performed.
