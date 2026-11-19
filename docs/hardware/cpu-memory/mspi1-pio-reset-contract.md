# MSPI PIO and NOR Reset Contract

Task bw-0167. This stage covers **saved original execution evidence and source analysis**. It did not change the production model or execution endpoint, and no new guest was run. Completion of the overall web installation, recovery, CFW, simulator, and integrated display goal was 13/29 (44.8%).

## Actual observations and static follow-on path

The 73 checks in `inspect_mspi1_pio_contract.py` compared pinned main, saved logs/reports, derived assets, HAL/SVD, and the caller path below. Inputs were the three originals from `mspi1-clear-all-main-01`. The saved stack_context was reused, so the same guest was not repeated without additional observation.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw |
| --- | --- | --- |
| PIO transfer function entry | `4E8944` | `4DB570` |
| CTRL C1 attempted write PC | `4E8A46` | `4DB672` |
| First saved return address (Thumb bit removed) | `47B724` | `476A0C` |
| Device command wrapper entry | `47B694` | `47697C` |
| Reset function entry above it | `47B3D4` | `4766BC` |

Comparing original function push/pop linked the return address at stack word 7 to the caller's BL. The wrapper frame layout and return address at word 21 were also linked to the next caller BL. The call relationships were not inferred merely because a stack value resembled code.

Current r1 points to a 24-byte descriptor prepared in actual RAM at SP+36. Its values are identical for the three inputs: byte 0..3 data length 0, offset 6 = 1 (TX branch), offset 12 = 1, and offset 14..15 = `0066`. Interpret each field together with original accesses to the relevant offset and the observed CTRL C1/INSTR 66. Do not extend this to proof that the entire latest HAL structure ABI is identical.

CTRL C1 selects START, SENDI, and TXRX with data length 0. The present stop is a command transmission **attempt**, not evidence that an SPI byte was sent or the device accepted it.

The original transfer function has a call passing STATUS(bit 1) mask 2/value 2 and subsequent interrupt-mask restoration code. Static inspection also confirmed the target's register read, mask, comparison, backward branch, and timeout-4 return body. The static path in the upper reset function contains transmission of 66, a delay call, then transmission of 99. The subsequent 99 path and completion polling have not actually executed yet. Public HAL `am_hal_mspi_blocking_transfer` shows the same broad sequence of start, FIFO processing, STATUS wait, and interrupt restoration.

## Manufacturer contract

Page 90 of [Macronix MX25U25643G v1.1](https://www.macronix.com/Lists/Datasheet/Attachments/8766/MX25U25643G,%201.8V,%20256Mb,%20v1.1.pdf) describes 66 as reset-enable and 99 as reset. Reset-enable is required before 99, and another command in between invalidates the enable. Ready time after reset depends on the preceding operation. This is documentary evidence for a candidate chip, not confirmation of the chip installed in the actual G2. The original also has other NOR candidates and fallback, so do not invent a JEDEC ID to satisfy a success condition.

The original PDF was saved outside Git at `simulator/mspi1-pio-research-01`: SHA-256 `1488ab399222ab2040e3c56fe8ba8b3ba624f19485a66c7b3558207167be2ae5`, 1,856,890 bytes. Text extraction from pages 90/93 was also preserved. Do not treat text extraction as verification of timing-table min/max columns or waveforms. Added pypdf 7.0.1 to the local analysis venv; the firmware execution engine was unchanged.

## Reusable engine review

Preserved and compared Git blobs/SHA for `Macronix_MX25R.cs`, `Micron_MT25Q.cs`, and `GenericSpiFlash.cs` at pinned Renode infrastructure commit `066a7f13c052215632d469c995c89aea37c573b1`. [`GenericSpiFlash`](https://github.com/renode/renode-infrastructure/blob/066a7f13c052215632d469c995c89aea37c573b1/src/Emulator/Peripherals/Peripherals/SPI/GenericSpiFlash.cs) treats 66/99 as unhandled parameterless command warnings. Connecting it unchanged therefore does not implement reset.

The engine also initializes backing memory bytes to FF. Blackwall has not obtained actual external NOR contents, so this default is not supplied as stock flash backing. The fixed MX25R device identity is not evidence of the actual installed chip either. At this point engine source is referenced only; it has not been copied into product code or connected to the model.

## Next implementation unit

1. Separate MSPI controller PIO state from NOR device state. START clears completion and becomes busy; update controller STATUS/CMDCMP only after actual command delivery in virtual time. Explicitly handle STATUS W1C, restart while busy, and power/clock/reset cancellation. Do not manufacture completion by polling count.
2. The first device profile is an explicit idle NOR reset scenario. Test 66 and 99, latch invalidation by an intervening command, and a separate flash-reset recovery state. Do not combine controller command-transfer completion and NOR internal reset completion into one event. Physical timing is unmeasured, so record selected virtual timing as an assumption and test stuck conditions too.
3. Expand FIFO data, JEDEC ID, status registers, and flash backing only after checking each one's provenance and need. Do not return 0/FF for unknown reads or pass firmware checks using an arbitrary ID. Supporting PIO C1 and 66/99 does not automatically authorize DMA, XIP, or program/erase.

This plan is not an implementation result. After implementation, the next native replay keeps the same conditions for the existing three originals and option-not-selected control. Do not overwrite PC/return values or skip hardware-check branches. Full boot, BLE, MSPI wire behavior, integrated display, and physical installation/recovery remain incomplete.

Review improvement: the initial 67 checks insufficiently verified the wrapper frame itself and polling helper body. Following review by an agent inheriting the parent model, added push/sub/add/pop and helper read/mask/compare/backedge/timeout checks; all 73 in `mspi1-pio-contract-02` passed. Actual subsequent execution of the two functions remains outside this static check.
