# PMIC BUCK Configuration Storage and Original ARM Initialization

Work bw-0151. Original stock and Faceclaw mains read configuration at `040f`, performed BUCK2 configuration and an enable request, then advanced to `0808`. Voltage, power rail, and GPIO/VSET response were not implemented or verified. Full main loop, display, and physical installation/recovery remain incomplete.

## Source contract

Nordic npmx commit `4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f` files `npm1300.h`, `npm1300_peripherals.h`, `npmx_buck.c`, and `npmx_buck.h` were pinned. All four originals were saved in private `simulator/npmx-buck-research-01` and checked against blob IDs and SHA-256 in the existing pinned Git tree. The [driver](https://github.com/nordicsemi/npmx/blob/4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f/drivers/src/npmx_buck.c) is BSD-3-Clause; the ADK headers' Nordic IC usage restrictions are separate. Original files were not copied into Git.

According to the [official voltage selection description](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/buck/doc/frontpage.html-output-voltage?contentId=RnDu_N7nSC0iWM3R4qoY9Q), initial output depends on external VSET conditions, and software voltage selection applies with BUCKSWCTRLSEL. Actual output voltage is not calculated and returned from configuration alone. GPIO selection and retention/PWM response are separate too.

| Address | Register | Selected profile initial stored value | Allowed stored codes |
| --- | --- | --- | --- |
| 0408/0409 | BUCK1NORMVOUT/BUCK1RETVOUT | 02/02 | 00–18 hex |
| 040a/040b | BUCK2NORMVOUT/BUCK2RETVOUT | 08/08 | 00–18 hex |
| 040c | BUCKENCTRL | 00 | 8-bit GPIO selection/inversion fields |
| 040d | BUCKVRETCTRL | 00 | 8-bit GPIO selection/inversion fields |
| 040e | BUCKPWMCTRL | 00 | 8-bit GPIO selection/inversion fields |
| 040f | BUCKSWCTRLSEL | 00 | bits 0–1 |
| 0415 | BUCKCTRL0 | 00 | bits 0–3 |

Voltage code `18 hex` (decimal 24) is listed in pinned ADK as `_3V30`, described as 3.3 V. SDK `NPMX_BUCK_VOLTAGE_MAX` is `17 hex` (23, 3.3 V). The model stores ADK code 24 too, but does not linearly convert it to 3.4 V. This does not claim the discrepancy is resolved for the actual PMIC revision or that SDK max may be extended.

0400–0407 are write-only tasks for BUCK1 enable/disable, BUCK2 enable/disable, BUCK1 PWM set/clear, and BUCK2 PWM set/clear. One byte 0 has no effect; 1 records a request. Request counts are **not counts of actual enable completion, PWM mode changes, or rail responses**.

## Model selection and boundary

A final optional `buckState` argument was added to both PMIC constructors:

- null: existing strictly unsupported state; BUCK access is not automatically allowed.
- guest-storage: all settings start unknown; only guest-written bytes can be read.
- source-reset-storage: explicitly declares the nine initial stored values above. This is not an actual OTP/VSET/GPIO or power-reset model.

Reads/writes of 1–8 consecutive configuration bytes are supported. The entire burst address and value are validated before application, so a reserved region or invalid code later in the burst cannot save only the preceding bytes. Values and diagnostic counts before/after failure were tested. Tasks accept only one byte and reject reads. 0410/0411 VOUTSTATUS, 0434 BUCKSTATUS, and reserved regions remain unsupported; settings or enable requests do not synthesize those states.

Reset initializes the fixture to profile values/unknown and empty request diagnostics. The existing strict model's pattern of separating register configuration from physical state remains.

## Original ARM execution

`tools/probe_pmic_buck_main.py` reuses the immediately preceding charger-status run as pinned input. It reverifies hashes/bytes of three original bundles/raw mains and changes only PMIC source portions, board selection, and observation output. Main, execution policy, initial SRAM/ITCM, and other model sources were preserved. Guest branches and returns were not forced. This starts at existing main reset; it does not newly establish ROM/full boot.

| Condition | Observed BUCK behavior | Next boundary |
| --- | --- | --- |
| Stock 2.4 / source-reset-storage | 040f read 00 → write 02, 040a write 15 hex, 0402 write 01 | Address write 0808, width 2 |
| Stock 2.3 / source-reset-storage | Same | Same |
| Faceclaw 38 / source-reset-storage | Same | Same |
| Stock 2.4 / guest-storage | Initial value unknown, no write | Existing address write 040f, width 2 |
| Stock 2.4 / null | No write | Existing address write 040f, width 2 |

Final stored values in three selected runs are `[2,2,21,8,0,0,0,2,0]`. Configuration writes total two bytes, task writes one, and task request array is `[0,0,1,0,0,0,0,0]`. This is BUCK2 software selection, storage of voltage code 21, and an enable request. It is not reported as verification of actual 3.1 V output or power-good. The two controls show an initial-value assumption is needed.

Stock 2.3 and Faceclaw were compared with the same model/runtime, allowing only main size differences. Seven inputs other than board selection match in the stock 2.4 three-profile comparison. ADC completions remained two each for VBAT/NTC/IBAT, returns remained four/11 bytes, and watchdog starts remained 0. Since PC matches the existing low-level IOM function, progress was assessed from payload, write history, and requested address. LastAddress 0402 is the previous pointer; the next request is LastValue 0808.

## Verification and limits

- Unit 01 preserved the red log failing due to the missing new constructor argument.
- BUCK unit 02: 198 passed, including existing state unit tests.
- Queued ADC unit 05: 401, scalar ADC unit 08: 408, watchdog unit 13: 240 passed.
- Original main 01: the five conditions above completed and were verified.
- Recovery feed 14: five ARM-function conditions compiled from pinned watchdog.h passed, retaining existing synthetic power/pin/DWT/hole assumptions.
- Saved audit 01: 205 passed. It compared source pins/declarations/reset, current model, original/full model source reconstruction, observation-only runtime, fills, raw logs, writes/requests, controls, regressions, and feed.

The first invocation of audit tool `verify_pmic_buck_evidence.py` failed before execution due to a syntax error in regex string concatenation, then passed after correction. Native tests were not rerun at that point. Evidence is preserved privately in `simulator/pmic-buck-unit-01`, `pmic-buck-unit-02`, `pmic-buck-main-01`, `pmic-queued-unit-05`, `pmic-adc-conversion-unit-08`, `pmic-timed-unit-13`, `recovery-pmic-feed-14`, and `pmic-buck-verification-01`. Docker ran sequentially and relevant source was not changed during execution.

[Nordic erratum 27](https://docs.nordicsemi.com/r/bundle/errata_npm1300_rev2/page/err/npm1300/rev2/latest/anomaly_300_27.html) describes a standby-current problem under initial software voltage-selection conditions on certain PMIC revisions. This model reproduces neither that analog result nor physical efficacy of the workaround. Actual G2 PMIC revision/VSET are unknown. Emulator success is not claimed to resolve that risk.

Next address 0808 is `LDSW1LDOSEL` in the pinned ADK. LDSW/LDO mode, voltage, enable, and GPIO settings need grouped investigation without mixing nPM1300 and nPM1304 revision-specific behavior. No new response is implemented yet.

Product progress remains 13/29 (44.8%). No glasses connection, RAM payload, OTA, permanent write, or Astra execution occurred. A read review by an existing non-Astra agent inheriting the parent model found no significant implementation error and confirmed retention of distinctions between enable requests/voltage codes and actual output, and ADK code 24 versus SDK max 23. Exact model ID, separate model-family review, and an unavailable transcript archive audit are not claimed complete.
