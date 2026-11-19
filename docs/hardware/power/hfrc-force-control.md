# HFRC Force Control and Subsequent Initialization

Status: limited verification complete for control model, seven native synthetic conditions, four existing-behavior regressions, and six original main combinations. This is not full boot, display, or real-device verification.

## Public evidence and behavior

`am_hal_clkgen_private_hfrc_force_on` in pinned Ambiq HAL `61b293a49db34030c545f99101f7ebf6a3050314` sets or clears MISC.FRCHFRC bit 0. The public header identifies CLOCKENSTAT.HFRCCLKEN as bit 30, indicating HFRC oscillator enable.

Native runner option `--hfrc-force-control` adds this control to the existing explicit clock response. It is disabled by default. It stores MISC while preserving existing HFRC2 force bit 5 and new HFRC force bit 0, and supplies HFRCCLKEN derived without delay from the bit 0 request. Other MISC bits, partial-width access, and status writes remain blocked. `force_writes` is the total MISC control writes allowed by the clock-response model, not a count of HFRC-only transitions or physical oscillator state changes.

This is a digital enable indication derived from the force request. It does not model actual warmup, frequency, stability, peripheral consumers, deep-sleep retention, or power. The general case where another consumer uses HFRC after force is released is unsupported. The existing clock profile's other synthetic states, initial values, and zero-delay assumption remain.

## Verification

Of seven conditions in `tools/verify_renode_mmio_guard.py --with-hfrc-force-control`, three for on, off, and simultaneous control with HFRC2 recorded completion sentinel. Four for reserved bits, byte writes, status writes, and disabled option stopped at the first unsupported access without executing the completion write.

Pre-addition test `hfrc-force-native-red-01/report.json` failed its expected completion because the existing model blocked the enable write. After connection, `hfrc-force-native-guard-01/report.json` passed all conditions. Public fields, offsets, and HAL operation existence were reverified by `verify_mcu_clock_sources.py --with-hfrc-force-control` (`hfrc-force-source-audit-01/report.json`).

The first stock 2.4 LP run `hfrc-force-main-stock24-lp-01/report.json` reached MISC=0xfbbfe1, HFRC forced=true, HFRC2 ready=true, then stopped at PC `0x5c1e6e` attempting to write `0x6d3d9` to MCUCTRL.LDOREG1 `0x40020080`. This subsequent voltage correction is not allowed by this control model.

The Python approximate executor remains stopped at the earlier SHCSR/MPU boundary. Native's additional MISC control, clock read, buck read, and different endpoint are explicitly distinguished; full execution equivalence or full firmware boot is not claimed.

No physical glasses access, flash, OTA, MRAM modification, or external publication occurred.

## Final verification material and remaining work

Six combinations of two stock versions and Faceclaw × LP/HP in `hfrc-force-main-comparison-01/report.json` passed. Final PC is `0x5ba8c6` for stock 2.3/CFW and `0x5c1e6e` for stock 2.4; all stopped at LDOREG1 write. The first stock 2.4 LP result was reused after verifying source, hash, and options.

The comparator explicitly checks native's additional geometry and selector one each, 2,048 clean-invalidates, three buck reads, two MCU mode reads, two MISC control writes, one clock read, and MISC=0xfbbfe1 relative to Python. It does not claim identical endpoints or all cumulative access counts.

Four existing default guard, nominal/no-ack clock, and GPU HP request regressions passed in `hfrc-force-native-regression-01/report.json`. Missing new-option prerequisites were rejected before reading input files.

An exception was found when the comparator's optional clock model was null. After reproducing it in `tests/test_startup_comparison.py`, it was fixed to treat absent/null alike. Red/green logs and post-fix normalized reverification of the existing six pairs are preserved in `hfrc-force-verification-01/`. This reverification did not rerun firmware.

Next are CORELDO trim correction and subsequent SPOT power-up order related to GPU power readiness. Actual voltage is not reproduced and calibration of the owned device has not been confirmed.
