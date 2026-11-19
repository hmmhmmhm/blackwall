# EN4B/RDCR model and original firmware's 4BYTE check

Task bw-0182 added a reset configuration fixture and an EN4B/RDCR state model. The actual indirect call target, received byte, bit 5 test, and caller return were checked in stock 2.4, stock 2.3, and the original Faceclaw main. **This does not implement 32-bit address array reads, a complete boot, or a display.** Product progress is 13/29, or 44.8%.

## Limited reset model

`configurationByte` defaults to -1 (unknown). Known inputs are limited to 0 or 8, representing only the manufacturer's reset default of 0 for volatile bits and the selected TB OTP bit 3. No assumption is made about the actual device's OTP value or initial configuration. A known input also requires an explicit MX25U25643G identity and a known status with WIP 0.

`CurrentConfigurationByte` combines the seed with the 4BYTE bit 5. Completion of B7, CTRL C1, and CFG 03010061 sets bit 5; completion of a 15, RX1 transfer supplies the current value to the FIFO. Unknown blocks both requests. No separate WEL prerequisite was added for B7: the manufacturer's procedure on p. 43 does not state one. This is neither a rule for all other NOR devices nor verification of physical behavior.

Repeated B7 preserves the same mode. RDSR, RDID, WREN, and NOP preserve the mode. A valid 66→99 sequence and owner reset clear bit 5 and return to the 24-bit reset state while retaining the TB seed. An incomplete transfer or clock abort does not set a new mode. EX4B, array reads, WRSR, and NV writes remain unsupported guards. General configuration storage that preserves arbitrary settings for resettable volatile bits was not implemented.

## Verification in the original firmware

The following sequence was observed in all three runs with known seed 0:

1. After the B7 transfer, the original caller receives 0.
2. The original WIP helper and polling return 0.
3. Immediately before the original BLX, R0 holds the RDCR helper's Thumb address.
4. That helper entry executes and reads the actual byte 20.
5. The original bit 5 test returns 1, and the caller also receives 1.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw |
| --- | --- | --- |
| Actual indirect call target | 47B83F | 476B27 |
| Helper entry | 47B83E | 476B26 |
| Byte received by original firmware | 20 | 20 |
| Original helper / caller result | 1 / 1 | 1 / 1 |
| Next strict command | 04 · CTRL C1 | Same request |

Values are hexadecimal. The callback target was confirmed through the actual register and consecutive entry observations, rather than left as a static candidate. The byte was read from R0 at the instruction following the original SP+8 byte load; the original bit 5 branch and return, and the caller after BLX, were observed. No PC, branch, or return value was forced.

Each of the three images completed EN4B once and RDCR once, with 1,160 transfers total, 1,153 ID operations, 2 status operations, and 1,156 FIFO operations. There were 345 selected events and no omissions. The existing 336-event prefix, scan matrix, and output snapshot also match. The control with unspecified configuration completed no EN4B/RDCR operations and retained the existing B7 strict boundary. It used the same runtime, differing only in the selected board seed.

The virtual mode flag and the original firmware's configuration readback test were confirmed, but this does not prove a physical NOR's 4-byte mode, address delivery above 16 MiB, memory backing, or physical data integrity. The existing synthetic memory, power, clock, and other assumptions still apply to execution from main reset. The stock 2.3 and Faceclaw model, board, and runtime are identical except for original image length.

## Verification and preservation

Under `simulator/` outside Git:

- `mspi1-address-mode-unit-01`: red evidence for the previous API without configurationByte.
- `mspi1-address-mode-unit-02`, `mspi1-address-mode-tb-unit-01`: 42 checks each for reset seeds 0 and 8. These cover completion timing, RDCR, repetition, entry without WEL, reset/TB, abort, and unsupported requests.
- `mspi1-address-mode-unknown-unit-01`: 5 checks for blocking unknown input.
- `mspi1-address-mode-stuck-unit-01`: 14 checks for incomplete operations. Unit total: 103 checks.
- `mspi1-address-mode-regressions-01`: existing WEL 36, fixed busy 22, and reset 26, totaling 84 checks.
- `mspi1-address-mode-main-01`: four combinations: the three original images and the unknown control.
- `mspi1-address-mode-verification-01/report.json`: 157 checks comparing the current model, original bytes, fixed fixtures, raw markers, actual callback target/byte/return, default boundary, and source-only observations.

The next stop is Write Disable 04. That command has not yet been executed, and its subsequent path is not reported as successful. No physical scan, connection, RAM execution, flashing, or persistent write was performed.

An agent inheriting the parent model reviewed the production code, tests, 157-check audit, and four main results and reported no further significant defects. The original firmware's bit check is distinguished from actual address transmission and physical mode. Astra, another model family, and a full transcript file audit were not used.
