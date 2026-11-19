# Read-Only Reset Fixture for the Trim Cache Region

Status: an offline fixture executing register reads and RAM cache flow in actual pinned main. It does not confirm physical device calibration, voltage, or normal boot.

## Scope established from actual code

Stock 2.4 `0x4952fc`–`0x49549c` checks a completion flag, stores fields from several registers in RAM cache, then sets the flag. The flag at `0x4952be` based on chip revision and this cache completion flag are different variables and are not equated.

PC-relative literals were decoded to identify 12 required registers in this region, including SIMOBUCK, LDOREG, VREFGEN, D2ASPARE, and PWRCTRL.VRSTATUS. Exact addresses, reset words, and field positions/masks are in the [pinned catalog](../../../tools/simulator-trim-reset-catalog.json). This catalog is not an actual device register dump.

## Provenance and documentation differences

The [CMSIS header](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/CMSIS/AmbiqMicro/Include/apollo510.h), [MCUCTRL definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/mcuctrl_regs.html), and [PWRCTRL definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/docs/apollo510/pages/pwrctrl_regs.html) from upstream `zephyrproject-rtos/hal_ambiq` commit `61b293a49db34030c545f99101f7ebf6a3050314` were used. Downloaded originals were checked against Git blobs and each file's SHA256 pinned in the catalog. They are preserved outside Git in `Blackwall/simulator/upstream/hal-ambiq-61b293a/`.

HTML reset values were combined with header field positions/masks. Initially generation stopped because SIMOBUCK2 HTML fields were missing from the header. The identified differences are VDDCINPREFSEL, VDDCACTLOWTOFFTRIMFINE, and VDDCACTHIGHTOFFTRIMFINE. All have documented reset 0, so they are recorded as zero contribution without guessing field positions. This difference remains in catalog `html_only_zero_fields` and runtime reports. If a field absent from the header has nonzero reset, the verifier rejects it. This handling is not generalized into proof that the entire register ABI matches.

`tools/verify_trim_reset_catalog.py` rechecks original SHA, register names, addresses, reset values, field positions/masks, and documentation differences. It uses only public source, without firmware or devices.

## Model boundary

`--trim-reset-fixture` can be selected only with both MCUCTRL and power models. The complete catalog SHA256 is also pinned. It supplies aligned four-byte reads at exactly 12 addresses and rejects other addresses, partial-width access, and all writes to these registers. It is not automatically applied to existing scenarios.

Public reset values may differ from a calibrated running device. Actual voltage, analog response, and valid device calibration are not supplied. Reports record `valid_device_calibration=false`, `hardware_verified=false`, `voltage_and_analog_behavior=not-modeled`, and catalog/source SHA.

## Actual input execution

`startup-zero-info1-rev-23-trim-reset-hypothesis` was run for stock 2.3, 2.4, and Faceclaw38. It read the 12 addresses 17 times total, executed through the instruction storing cache completion flag, then stopped at the next 0x4002037c read. PC is 0x4895b8 for 2.3/Faceclaw and 0x4954a0 for 2.4.

Results and source verification reports are outside Git in `Blackwall/simulator/trim-reset-cache-01/`. Seventy-four runner tests and three scenario tests passed, including write rejection at all fixture addresses, partial-read rejection, catalog tampering rejection, and different source SHA rejection. Full boot, display transport, actual installation, and recovery compatibility remain incomplete.

```sh
python3 tools/verify_trim_reset_catalog.py \
  "$HOME/Library/Application Support/Blackwall/simulator/upstream/hal-ambiq-61b293a" \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-trim-source-check.json"
```
