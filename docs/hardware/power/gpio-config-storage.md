# GPIO Protection Key and Pin Configuration Storage Model

Status: public source, layout, and call analysis complete. The digital storage model is tested separately. Full main boot, display, and actual electrical behavior remain incomplete.

## Confirmed evidence

`am_hal_gpio_pinconfig` in pinned [Apollo510 HAL](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/am_hal_gpio.c) performs PADKEY=0x73, the specified PINCFG write, then PADKEY=0 in a critical section. GPIO header PADKEY description and key enum also correspond to 0x73. GPIO_BASE 40010000, contiguous PINCFG0..223 offsets 0..37c, and PADKEY offset 400 were checked by compilation. Public defined-field mask for all 224 PINCFG registers is 0x0c7fffff.

HAL c/h were checked against Git blob SHA1 and preserved outside Git. Private `gpio-research-01/source-report.json` records provenance, hashes, and 225 offset compilations. The public offset/mask table is `gpio-register-map.json`. Instructions around the actual stopped key write in three mains also correspond to key 73 → indexed store → key 0 → PRIMASK restoration. Candidate static decoding is not interpreted as complete function/ABI recovery or verification of every pin.

## Model boundary

`--gpio-config-storage` is a separate opt-in. Initial state is a conservative synthetic locked state, not verified actual chip reset state. Only keys 73/0 are allowed. Aligned PINCFG0..223 DWORD writes while unlocked store values and write counts if no bits outside defined fields are set. Readback is allowed only for guest-written pins; reads of pins with unknown initial values are blocked. PINCFG readback is also possible while locked.

PADKEY reads, other keys, partial widths, reserved gaps, and input/output/IRQ registers remain blocked. Writes while locked stop the emulator as a diagnostic policy; this does not claim the actual chip raises an exception on the same access. Storage does not execute pin functionality. Function-select validity, drive strength, pull, pad electrical state, pin-mux output, external connections, input, and interrupts are not verified or implemented. Actual board pin count or connections are not equated with public SoC register count.

## Virtual guard tests

Nineteen conditions in private `gpio-config-native-01/report.json` passed. Seventeen new conditions cover unlock/write/lock/readback, writes while locked, invalid key, key read, reserved bits, partial key/pin writes, final pin 223, out-of-range pin/reserved gap/input read, writes after relocking, repeated writes, initial/unwritten pin reads, and option not selected. Two existing GPU off-sequence and ring-phase blocking conditions also passed.

## Four main runs

In stock 2.3/2.4 and CFW, the guest wrote pin1=3, pin3=3, pin4=0x93. There were six key writes, three config writes, and zero config reads; all ended relocked. The next access was a DWORD read at 0x40010530. Compiling the pinned header confirmed correspondence to GPIO.MCUN0INT0EN offset 530. Initial value and interrupt behavior are unimplemented and 0 is not supplied. Stock 2.4 control without the option was blocked at the previous PADKEY 0x40010400 write.

Private `gpio-config-verification-01/final-verification.json` compared source snapshots for native 19 and main 4 with current source. Pin functions, external signals, full boot, and integrated display remain incomplete. Next analyze reset evidence for GPIO interrupt enable and the enable/status/clear relationship.
