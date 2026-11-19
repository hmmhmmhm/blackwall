# GPIO38/IRQ57 input implementation plan

bw465. This extends GPIO input within the approved scope of virtual G2 emulator development. It does not include physical writes, completion of normal GAF, or scope changes.

The basis is PINCFG38=0x93 and bank1 enable=0x40 in three existing original captures, and bw464 callback/vector/context. eIntDir bits 7:6 value 2 corresponds to LO2HI in the existing pinned GPIO header. Initial low is a virtual scenario choice, not a physical idle reading.

The approach adds default-off pin38 and IRQ38 output to existing `BlackwallGpioInterruptIdle` pending/mask/clear contracts. A separate GPIO model duplicates bank ownership, while direct IRQ injection into CPU cannot verify actual status/clear, so neither is selected. Existing 117/27 state and clear remain independent. No global refactor or existing default-profile change.

Verification sequence:

1. Preserve native red for absent new constructor/input API.
2. Test opt-in, configuration rejection, rising/held/falling, mask/unmask, W1C, concurrency with 117/27, reset, and IRQ57 wiring in actual Renode. Run the existing BLE unit contract too.
3. Reuse original reset/hold from the existing runtime builder and supply only an explicit GPIO38 edge. Confirm pad/enable, unchanged CPU/SRAM before injection, original ISR/registered callback, IPSR73, original clear, and exception return. Do not change gate/timestamp.
4. Compare three originals and no-input/default-off boundaries and confirm owned-process cleanup. Do not report success of GAF computation or natural FIFO sample consumption.

Proceed within existing conversation approval for emulator development. Apply the brainstorming skill's design-review method without adding authorization for new features, external publication, or physical devices; do not create a separate commit.

All four stages completed. Results and limitations for three original IRQ57/exception returns, two controls, unit/regression, and cleanup are recorded in the [execution record](imu-gpio38-runtime-ingress.md).
