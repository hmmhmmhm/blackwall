# PMIC Event and Interrupt Register Initialization

bw-0137. Original event initialization was executed after PMIC restore. This is a digital-register experiment under explicit virtual idle state; physical events, PMIC GPIO, Apollo GPIO, and IRQ connection were not verified.

## Contract and model

[Nordic's official event register documentation](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/ctrl_reg/doc/main-registers.html) describes W1S/W1C behavior for event SET/CLEAR and interrupt enable SET/CLEAR. The pinned ADK and original register table were also compared. Eight banks are supported:

| Event SET address | Group | Model's defined bit mask |
| --- | --- | --- |
| 0x0002 | ADC | ff |
| 0x0006 | Charger temperature | 3f |
| 0x000a | Charger status | 3f |
| 0x000e | Charger battery | 07 |
| 0x0012 | ShipHold | 0f |
| 0x0016 | VBUS voltage | 3f |
| 0x001a | VBUS thermal/USB | 3f |
| 0x0022 | GPIO events | 1f |

For each base, +1 is event clear, +2 enable set, and +3 enable clear. These banks open only when `interruptState="explicit-idle"` is added to `BlackwallPmicRestoreProbe`. Declared starting state is events=0 and enable=0; subsequent W1S/W1C operations change state. Only one-byte SET alias reads are supported. CLEAR alias reads, reset tasks, and reserved addresses are unsupported.

The model applies only defined bits. Ignoring reserved bits in FF writes is the declared virtual mask policy, not verified silicon behavior. Software event SET can create synthetic state but does not generate actual sensor events. `DigitalIrqPending` is only the logical OR of events & enable, not GPIO voltage, PMIC output polarity, or an Apollo IRQ signal. It is not wired.

The existing IRQ-unsupported default remains. Zero internal diagnostic arrays in default mode are not interpreted as actual event state; bank accesses remain blocked. History in selected mode is limited to 64 reads/64 writes. PMIC configuration writes beyond the seven-byte configuration profile, measurement, charging, and power behavior remain unsupported.

## Original execution

`tools/probe_pmic_interrupt_main.py` derives pinned bw136 inputs with only model replacement, explicit board arguments, and peer diagnostics. Original main, fill, probe, memory policy, functions, and returns are unchanged.

Stock 2.4, 2.3, and Faceclaw each executed these two writes in order for every group:

1. FF to interrupt enable clear.
2. FF to event clear.

Sixteen register writes and 26 Finish calls were observed in total, including existing restore queries. At completion all eight event and enable banks are 0 and logical pending is false. This is a result from initial idle. A separate virtual test created nonzero events/enables to verify partial clear, pending changes, and separation between banks.

The stock 2.4 control omitting interruptState retains zero register writes and the previous first 0005 stop. No automatic connection was added to the default main runner.

## New boundary: PMIC GPIO1 output mode

The next request across the three originals was `06 01 05`. FIFO load/store instructions in source were compared with low 24 bits 0x050106 of R1 at the stop. Guard LastValue records only request address 0x0601, so data 05 was not established from that alone.

In the pinned ADK, GPIOMODE1 address 0x0601 mode 5 is GPOIRQ. This is consistent with the original **intending to configure PMIC GPIO1 as interrupt output**. The model rejected that write. It alone does not establish G2's Apollo GPIO number, wiring, pull, open-drain, polarity, or ISR behavior. Current public npmx GPIO configuration function order is not assumed identical to the original. Additional GPIO source was separately preserved in `npmx-interrupt-research-01` with commit/blob/hash.

CPU stops at the same IOM CMD point (stock 2.4 PC 0x58236c, 2.3/CFW 0x57b014). This time it stopped on a different request after 16 initialization writes.

## Verification material and limits

The 83 checks in `pmic-interrupt-unit-01/report.json` add per-bank W1S/W1C, mask, pending, partial clear, reserved-address rejection, history boundaries, reset, and explicit-state checks to the existing 31. `pmic-interrupt-main-01/report.json` contains three originals and one unsupported control. The 88 checks in `pmic-interrupt-verification-01/report.json` confirmed raw logs, markers, pinned inputs, model differences, default boundary preservation, exact 16 requests/state, FIFO data 05 evidence, masks, source pins, and identical stock 2.3/CFW conditions.

As requested by independent GPT-6-family review, the next request's address and data were verified separately. The reviewer did not separately execute native results; the parent audited saved material. No separate transcript archive comparison, Astra, physical access, or external publication occurred. The default-wait wording in the previous work note was an assumption written before polling results; the final result is normal completion of the actual same handle and successful unsupported control.

Full boot, display, and GPIO/IRQ lifecycle remain incomplete. UART TX, ISR, and CQ pairs are also 0. Product completion remains 13/29. Next investigate subsequent PMIC GPIO1 configuration registers and original Apollo GPIO registration path, and state the conditions needed for signal connection.
