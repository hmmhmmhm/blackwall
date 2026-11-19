# Digital Storage of PMIC Charger Configuration and Unknown State

bw-0139. Configuration registers and partially known bits were modeled without creating battery voltage or charging-success state. No physical device, Astra, or external publication was used.

## Model scope

The charger configuration bank opens only when `chargerState="guest-storage"` is explicit. Four bytes 0x0308–0x030b from the existing profile are initialized as before. Other configuration remains unknown until guest writes. Original-written values are supplied as exact byte readback.

Supported digital settings:

- 0x0304/05: charging enable SET/CLEAR, two defined bits.
- 0x0306/07: recharge/NTC disable SET/CLEAR, two defined bits.
- 0x0308–0x031b: current codes, termination/trickle settings, NTC/die-temperature thresholds.
- 0x033c: charger configuration bit.
- 0x0350: low-voltage charging permission bit.

Field masks were compared against pinned ADK. For 0x0350, absent from the older ADK, the BCHGVBATLOWCHARGE bit 0 definition from [current Nordic charger documentation](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/charger.html?contentId=WJYmxlCCYDqgCuBATtkdMw) is used. Storing numbers does not implement physical charging, voltage, heat, or protection. The model does not verify every physically possible current/threshold-code combination either.

SET/CLEAR aliases start unknown. Only written 1 bits become known; the rest remain unchanged. For example, writing 2 to 0x0307 establishes only that DISABLENTC bit 1 is 0; recharge bit 0 remains unknown. Alias reads are rejected until both required bits are known. Only SET alias reads are supported. Unknown is not returned as 0.

Ordinary one- to two-byte configuration bursts are stored atomically after checking every address/mask and history capacity. An invalid second byte cannot change only the first. Byte-write counts and transaction counts are distinguished. Status, battery measurement, error queries, task execution, OTP writes, and timers remain unsupported. Default-mode 0x0350 blocking remains.

## Four original runs

`tools/probe_pmic_charger_main.py` changes only model, explicit board arguments, and diagnostics from pinned bw138 input. Original main/fill/probe, CPU policy, and function execution remain. Stock 2.4, 2.3, and Faceclaw ran under the same conditions.

After 17 existing writes, the three originals performed:

| Address | Value | Confirmed digital meaning |
| --- | --- | --- |
| 0x0350 | 1 | Set low-voltage charging permission |
| 0x0307 | 2 | Clear DISABLENTC bit 1 |
| 0x0013 | 8 | Clear watchdog warning event |
| 0x0014 | 8 | Enable that warning interrupt |

There were 21 register-byte writes and 31 Finish calls total. Charger transactions numbered two. Charger alias known mask is `[0,2]`; full charging-enable state remains unknown. Warning enable is 1 but event is 0, so logical pending was false. Physical signals/IRQ were not connected.

Stock 2.4 control omitting chargerState stopped at the existing 0x0350 request.

## Next boundary: separate PMIC watchdog

The next actual request is `07 05 0a`. Original FIFO load/store and low 24 bits 0x0a0507 of stopped R1 were compared. 0x0705 is PMIC TIMERCONFIG; in pinned ADK, 0x0a is mode 2 (WATCHDOGRESET) plus prescaler bit 3. All three originals requested this write; the current model rejects it.

This is a timer configuration **request**. TIMERSET, target commit, start, kick, warning, expiry, and reset were not observed. The Apollo internal watchdog and separate PMIC watchdog are not treated as one device. PMIC reset effects during recovery wait require future investigation. The same path appears in stock, so Faceclaw is not interpreted as adding new watchdog behavior.

## Verification and remaining work

The 201 checks in `pmic-charger-unit-01/report.json` add partial-known aliases, exact readback, two-byte bursts, atomic invalid bursts, status/task rejection, reset, and default blocking to 162 existing checks. `pmic-charger-main-01/report.json` records three originals plus one default control. The 110 checks in `pmic-charger-verification-01/report.json` compared raw markers, pinned main/image, exact model replacement and board arguments, actual write order, partially known masks, subsequent watchdog request, default boundary, and 25 source masks.

Independent GPT-6-family reading review confirmed unknown state, atomicity, and byte/transaction distinction. The parent separately audited four final native results; no separate transcript archive comparison occurred. Product conditions remain 13/29. Full boot, display, battery/sensors, and GPIO/IRQ lifecycle are incomplete. UART TX, ISR, and CQ pairs are also 0.

Next investigate PMIC timer configuration, actual start conditions, clock, target, kick/expiry, and how original boot/recovery code handles the PMIC watchdog.
