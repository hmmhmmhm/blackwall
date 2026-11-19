# PMIC VBUS Configuration Storage and Apply Request

bw-0143. The original main's strict 0x0201 boundary was investigated and an optional digital subset added.

## Source contract

[vbusin.c](https://github.com/nordicsemi/npmx/blob/4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f/drivers/src/npmx_vbusin.c) and [vbusin.h](https://github.com/nordicsemi/npmx/blob/4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f/drivers/include/npmx_vbusin.h) from Nordic npmx commit `4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f` were checked against existing tree Git blob IDs and SHA-256, recorded in private `npmx-vbus-research-01/sources.json`. Existing ADK nPM1300 header is research material for addresses, masks, and OTP initial-value comments and is not copied as code. Existing research conditions retain driver SPDX BSD-3-Clause and separate ADK license scope.

| Address | Behavior | Optional model |
| --- | --- | --- |
| 0201 | Host input-current limit configuration | Store/read back only guest-written code |
| 0200 | Configuration selection task | Record request count when current setting is known |
| 0203 | Suspend-control configuration | Store/read back guest-written bit 0 |
| 0205/0207 | CC/VBUS status | Unsupported; unknown is not filled with 0 |

0201 is four bits, but codes 2–4 are marked reserved and rejected by the selected model. Supported codes are 0, 1, 5..15. This conservative allowance policy is not proof of physical register reserved behavior. OTP-derived initial values remain unknown, and pointer reads before guest writes are rejected. 0200=0 is a no-op; 0200=1 records only a request, requiring known current configuration. Actual input current, power rails, VBUS detection, suspend activation, voltage, and events are not generated.

## Implementation and verification scope

Activated only with optional `vbusState="guest-storage"` in `renode-pmic-restore-probe.cs`; `renode-pmic-timed-probe.cs` passes the option through. Omitted default retains the existing strict boundary. Only STOP-based single-register writes/readback are supported; task reads, bursts, and status are rejected. Masks, values, and history limits are checked first, preserving stored values and apply counts on rejection; Reset returns to unknown.

Private `pmic-vbus-unit-01/report.json`: 252 checks passed including existing 201. They check initial unknown, legal/reserved codes, suspend, apply prerequisites/zero task, invalid-write atomicity, status/task read blocking, Reset, and default strict. This is not actual charging testing.

Private `pmic-vbus-main-01` results cover three originals plus one default control: all three recorded current code 5 (500 mA setting in source), one 0200 apply request, and two VBUS writes. Last writes were 0201=5, 0200=1. Next strict boundary is write 050a; PC is 58236c for stock 2.4 and 57b014 for stock 2.3/Faceclaw. Additional existing charger/interrupt subset writes also executed naturally in this interval. Suspend remains unknown, not actual state 0. Default control retained existing 0201 boundary. Timer config 0a/target 3c00/strobe 1, Start 0/running=false.

After optional constructor extension, `pmic-timed-unit-06` 240 checks and `recovery-pmic-feed-07` five ARM cases were reverified. Default model and recovery fixture do not enable the VBUS option. Recovery fixture was corrected to replace root/timer sources together with current versions, avoiding mixing the old pinned root with the new constructor. The 68 checks in `pmic-vbus-verification-01/report.json` compared source snapshot, raw logs/reports, original main invariance, default boundary preservation, identical 2.3/CFW conditions, exact configuration history, upstream source hash/blob, and latest feed evidence. Independent GPT-6-family review confirmed the distinction between apply request and actual current application. No transcript archive comparison occurred. Full boot, app loop, display, and real-device installation/recovery completion are not claimed.
