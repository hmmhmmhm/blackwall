# PMIC ADC Configuration Storage

bw-0144. This is an nPM1300 ADC register subset separate from Apollo510 ADC.

## Exact addresses and contract

The [official ADC register documentation](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/saadc/doc/frontpage.html?contentId=5owliBBpCrxzvTvnK6iS3A) and existing research material for pinned npmx commit `4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f` were checked. ADK header and adc.c in `npmx-research-01/sources.json` were rechecked against SHA-256 and tree Git blobs. Base 0x500 + offset 0x0a is ADCNTCRSEL, not LDSW base 0x800 offset 0x0a. Existing restore-profile NTC selection interpretation remains.

| Address | Meaning | Mask | Initial read condition |
| --- | --- | --- | --- |
| 0509 | VBAT automatic/burst configuration | 03 | Existing fixture 00 retained |
| 050a | NTC selection | 03 | Existing fixture 01 retained |
| 050b | NTC/die temperature automatic interval configuration | 0f | Unknown until guest write |
| 050d | Delay configuration | ff | Unknown until guest write |
| 0524 | Current measurement enable configuration | 01 | Unknown until guest write |

Initial fixtures are not values read from physical G2. NTC code 3 selects 100 kOhm in source, not proof of actual thermistor resistance or measured temperature. Storing configuration generates no conversion, timer, or event.

## Model scope

Optional `adcState="guest-storage"` is required to allow configuration writes. Single-register writes and readback after STOP are supported. Unsupported task/result/status values are not filled with 0. Automatic interval-update task is also unsupported. Mask and history are checked first, so invalid writes do not change stored values or counts. Reset returns to the existing two fixtures and other unknowns. Default retains existing write blocking.

`pmic-adc-storage-unit-01/report.json` passed 310 checks: existing 252 and 58 new. They check storage/readback, initial unknown, atomic mask rejection, task/result read/write blocking, burst blocking, returned-array copying, Reset, and default strict.

`probe_pmic_configuration_main.py --component adc` changes only PMIC source, selected options, and diagnostics from pinned VBUS main inputs. Original main bytes, CPU policy, synthetic assumptions, and call path remain. Three originals plus one default control in private `pmic-adc-storage-main-01` completed.

All three originals have configuration list `[0509,050a]`, values `[00,03]`, and exactly one ADC configuration write. After writing 050a=3, the next strict cause is write 0e02 (width 3). Guard LastAddress=050a is the previous pointer; rejected new address is identified as LastValue=0e02. PC is 58236c for stock 2.4 and 57b014 for stock 2.3/Faceclaw. Since this is the same IOM transfer point, logical progress is judged using actual register history and strict cause, not PC alone. Default control retains blocked 050a write, ADC writes 0, and `[00,01]`. Original timer remains Start 0/running=false. Other ADC settings remain unknown because they were not written. This is not yet full ADC initialization, conversion, sensor measurement, full boot, display, or physical verification.

## Final regression and audit

After adding the constructor option, `pmic-timed-unit-07` virtual timer 240 checks and `recovery-pmic-feed-08` five pinned recovery-feed ARM cases were reverified. The latter retains explicit power/pins/frozen DWT/status-hole mocks and is not a full recovery-boot run.

The 75 checks in `pmic-adc-storage-verification-01/report.json` compared raw logs/reports for three originals plus control, pinned main bytes, source snapshot, exact ADC addresses/values/one write, last history, next strict 0e02, default 050a boundary, identical 2.3/CFW model conditions, upstream SHA/blob, and latest unit/feed source. Independent GPT-6-family review cautioned against claiming full ADC completion solely from runner writes>=1, so saved audit explicitly states exact `[0509,050a]`/`[00,03]`/writes 1 and 050a=3 history. No transcript archive comparison occurred. Overall product fulfillment remains 13/29.
