# Guest Configuration Storage for PMIC GPIO and the Next Charger Setting

bw-0138. A model was added that stores only GPIO configuration written by the original, without assuming pin state. No physical device, Astra, or external publication was used.

## Implementation scope

Explicit `gpioState="guest-storage"` in `BlackwallPmicRestoreProbe` supports:

| Address range | Item | Allowed values |
| --- | --- | --- |
| 0x0600–0x0604 | GPIO0–4 mode | 0–9 |
| 0x0605–0x0609 | Drive strength | 0/1 |
| 0x060a–0x060e | Pull-up | 0/1 |
| 0x060f–0x0613 | Pull-down | 0/1 |
| 0x0614–0x0618 | Open-drain | 0/1 |
| 0x0619–0x061d | Debounce | 0/1 |

Addresses and fields were checked against pinned Nordic ADK and public GPIO source. Values remain unknown and reads rejected until the guest writes. Afterward only exact one-byte readback is allowed. Values are validated before state changes, known-address/value arrays are copied, and reset returns them to unknown.

Pin status at 0x061e and reserved addresses are unsupported. Storing pull, drive, and debounce values does not implement actual resistance, voltage, current, or timing. A flag observing GPIO1 mode 5 is also only configuration intent. PMIC output signals were not connected to Apollo input, NVIC, or ISR. The existing unsupported default mode remains.

## Original results

`tools/probe_pmic_gpio_main.py` derives pinned bw137 inputs. It changes only model replacement, explicit board arguments, and peer diagnostics; original main/fill/probe/memory policy, instructions, and return values remain.

Stock 2.4, stock 2.3, and Faceclaw all performed the following after existing seven-byte restore and 16 IRQ initializations:

- Wrote 5 to GPIO register 0x0601 and finished.
- This was the only known GPIO setting; its mode is consistent with GPOIRQ.
- Then stopped unsupported while attempting to write 1 to 0x0350.

There was one GPIO write, 17 register writes total, and 27 finishes. Events/enables were 0 and logical pending was false. The stock 2.4 control omitting gpioState stopped at the existing 0x0601 request.

Original 2.4 static caller calls GPIO configuration function 0x4fee6e at 0x500ade, then proceeds to the next initialization. Actual Apollo GPIO number, polarity, pull, edge, and callback were not determined on this path. Since the new endpoint is subsequent PMIC charger configuration, results before this stop are not considered completed GPIO wiring.

## New boundary and material version difference

New request bytes are `03 50 01`. Since the guard records only address, the lower 24 bits 0x015003 of actual stopped R1 were separately checked against original FIFO LDR/STR instructions. All three originals made the same request. Stock 2.4 direct writer 0x500e50 also specifies address 0x0350 and data 1.

[Latest Nordic charger documentation](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/charger.html?contentId=WJYmxlCCYDqgCuBATtkdMw) defines BCHARGER base 0x0300 + BCHGVBATLOWCHARGE offset 0x50 and enable bit 0. The request is therefore consistent with enabling charging of a low-voltage battery. This feature is absent from the pinned older ADK register structure; omission in old source is not taken as register absence.

This is a register write request. Reading OTP to determine a reset value differs from writing OTP; this request is not classified as an OTP/MRAM permanent write. Actual power, charging, persistence, and target silicon revision were not verified. The model still rejects the request. Because it was also observed in stock, it is not interpreted as behavior newly added by a Faceclaw patch.

## Verification and next work

The 162 checks in `pmic-gpio-unit-01/report.json` include existing 83 plus unknown/readback for 30 settings, value rejection, state preservation, copying, reset, and unsupported default. `pmic-gpio-main-01/report.json` covers three originals and one default control. The 79 checks in `pmic-gpio-verification-01/report.json` checked raw logs/markers, pinned main/image, base/derived hashes, model/board differences, actual write order/values, subsequent request, default boundary, and identical stock 2.3/CFW conditions. Static addresses/instructions are preserved in `pmic-gpio-source-01/report.json`.

Independent GPT-6-family reading review confirmed the distinction between configuration intent and physical signal. The parent separately audited final four original results. No transcript archive comparison was performed. Full boot, integrated display, sensors, and GPIO/IRQ lifecycle remain incomplete; UART TX, ISR, and CQ pairs are 0. Product completion remains 13/29.

Next, investigate PMIC charging initialization registers together against official specifications and original code, and define a digital configuration model that does not reproduce actual charging. Apollo GPIO connection remains unknown until the original registration path is identified later.
