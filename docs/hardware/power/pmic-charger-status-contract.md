# PMIC Charger Status Read Contract Investigation

Work bw-0149. Static investigation interpreting the next boundary `0x0334` in original ARM main execution. No glasses connection, new ARM execution, or peripheral behavior change occurred. Existing runs were not restarted.

## Confirmed boundary

Stock 2.4, stock 2.3, and Faceclaw runs in `pmic-queued-main-01` all stopped at `peer-write-unsupported`, requested value `0x0334`, width 2. These are two bytes `[03,34]` specifying a register address, **not a two-byte status-data read**. No charger status data had returned at that point. LastAddress may be the previous pointer, so request value, operation, and width are checked together. PC alone does not identify the upper PMIC caller.

## Registers established from source

The [ADK header](https://github.com/nordicsemi/npmx/blob/4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f/adk/npm1300.h) from Nordic npmx commit `4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f` was compared with the [official register table](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/charger.html-topic?contentId=_9bxKOxsR9u8_zXhcOKwyQ). All items below are one-byte read-only status with documented reset 0. Masks are unions of defined fields, not measured actual bus responses for reserved bits.

| Address | Name | Defined field mask | Meaning |
| --- | --- | --- | --- |
| 032d | BCHGILIMSTATUS | 01 | Battery discharge-current limit status |
| 0332 | NTCSTATUS | 0f | cold/cool/warm/hot comparison status |
| 0333 | DIETEMPSTATUS | 01 | Die temperature upper-limit comparison status |
| 0334 | BCHGCHARGESTATUS | ff | Battery detection, charging phases, temperature pause, supplement |
| 0336 | BCHGERRREASON | 7f | Latched charging-error causes |
| 0337 | BCHGERRSENSOR | ff | Sensor state latched on error |

Bits 0–7 of 0334 are BATTERYDETECTED, COMPLETED, TRICKLECHARGE, CONSTANTCURRENT, CONSTANTVOLTAGE, RECHARGE, DIETEMPHIGHCHGPAUSED, SUPPLEMENTACTIVE in order. 01 with only bit 0 set indicates battery detection, not by itself charging, full charge, or a normal power system.

**0335 is reserved.** A two-byte request from 0334 does not arbitrarily fill the following byte with 0. 0336/0337 are adjacent error bytes, separated from 0334 by the reserved area. Documented reset 0 also does not establish normal state at the current execution time. Physical state may differ with prior configuration writes, VBAT/NTC/IBAT results, and charging FSM.

## Official driver and original ARM comparison

Status, NTC, and die-temperature getters in [npmx_charger.c](https://github.com/nordicsemi/npmx/blob/4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f/drivers/src/npmx_charger.c) each read one byte. `npmx_charger_errors_check` reads two bytes from 0336 and may write clear and release tasks if errors exist. **The name errors_check is not classified as read-only.** This upstream-function investigation was host-side static file reading; the function was not called on a device.

After validating three pinned bundles with `load_pinned_main`, byte agreement of full raw main and existing execution inputs was confirmed. Exactly one 20-byte function candidate of the following form exists in each main:

| Input | Candidate function start | Backend call target |
| --- | --- | --- |
| Stock 2.4.0.24 | 580566 | 581128 |
| Stock 2.3.0.24 | 57d52e | 57e0f0 |
| Faceclaw 38 | 57d52e | 57e0f0 |

The candidate sets `r2=caller buffer`, `r3=1`, `r1=0334` and calls the backend through a pointer. The 20 bytes are identical across three inputs; the immediately following candidate also calls the same backend with `r3=2`, `r1=0336`. This is static evidence that original ARM also has wrappers reading a single status byte and an error pair. It does not prove symbol names, current native call stack, or entire upstream-source error-handling equivalence. In particular, dynamic call tracing has not yet confirmed that current execution originated in this wrapper.

## Scope of the next model

The recommended path retains default unsupported state in the existing strict model and adds an **explicitly selected status snapshot**. Treat six registers as one contract while rejecting reserved areas and writes. This investigation alone does not report a snapshot model implemented or main boundary advanced.

Compare:

1. No snapshot selected: reproduce current 0334 address-write block.
2. Documented reset snapshot: declare six status values 0 and observe effects of the initial-value assumption.
3. Battery-detected, not-charging snapshot: declare 0334=01 and others 0 as a synthetic scenario. Review alongside existing discharge ADC fixture without presenting it as actual normal state or charging FSM.

Full charging FSM implementation must interact with actual power, temperature, VBUS, charging enable/disable, and error tasks, and is distinct from a fixed snapshot. A snapshot alone does not allow error tasks or implement automatic charging. Initial tests include RO-write rejection, reserved-area rejection, 0336 error pair, STOP/repeated START, state preservation across failure, and differences in original execution by snapshot.

## Reproduction and evidence

Four investigated files are preserved as originals in private `simulator/npmx-charger-status-research-01` and checked against existing pinned Git tree blob IDs and SHA-256. Nordic-IC usage restrictions in the ADK header are not reduced to a general BSD license. The driver is BSD-3-Clause. Originals were not copied to Git.

`tools/inspect_pmic_charger_status.py` checks source pins, RO declarations/offsets/resets/fields, getter read lengths, original wrappers, and existing native termination logs. It launches no new Docker, guest, or device.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/inspect_pmic_charger_status.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  "$HOME/Library/Application Support/Blackwall/simulator/pmic-charger-status-contract-01"
```

Saved result: `private:simulator/pmic-charger-status-contract-01/report.json`, 56 checks passed. Do not reuse the same path or rerun completed results without reason. These are not counts of new peripheral behavior or boot-pass tests. Original main loop, integrated display, and physical installation/recovery remain incomplete; product progress remains 13/29 (44.8%).
