# ADC power request in the original bootloader

Status: bw526 verification in progress. This does not verify physical power or analog accuracy.

After actually writing ADC auto-calibration bit 0, the original 2.4 bootloader sets only ADC bit 13 in the shared power request. Buck start requests, overrides, and response transitions were all 0 then. The existing model rejected the request because it required both auto-calibration disabled and buck active.

Pinned SDK `hal-ambiq-61b293a/am_hal_pwrctrl.c` function `am_hal_pwrctrl_periph_enable` handles per-domain requests and status waits without a buck prerequisite for ADC. It explicitly specifies crypto's OTP condition and separate GPU order. This does not establish initial LDO voltage or stabilization time on physical G2 hardware.

The change removes only buck-active conditions from two ADC dispatch points in the shared register. Auto-calibration disable, explicit active/stuck-off response profile, single-domain change, partial-write blocking, and existing gates for other domains remain. Buck phase and CPU branches are not forced during execution. The existing limitation of a zero-response-delay digital functional model also remains.

## Verification material

- `private:simulator/original-boot-adc-entry-native-bw526-01`: original ARM state immediately before request.
- `private:simulator/boot-adc-cold-red-bw526-01/report.json`: previous model rejected the original ADC request under both profiles.
- `private:simulator/boot-adc-cold-green-bw526-01/report.json`: both corrected-candidate response profiles passed 44 checks total. This is a C# register-contract test, distinct from ARM/analog tests.
- `private:simulator/boot-adc-warm-regression-bw526-01/report.json`: all 20 existing conditions passed.
- `private:simulator/original-boot-adc-cold-native-bw526-01/frontier-proof.json`: actual original execution had one ADC request and response each, status on; buck off and requests/transitions 0 remained. After 13,789,871 instructions, write 1 to 0x40004044 at PC 0x426fc4 was strictly blocked. Code/system protection and CFSR/HFSR errors 0. Main entry not reached.

## Cleanup

Twenty synthetic guest ELFs totaling 676,864 bytes and two guest boot dumps identical to the original totaling 299,546 bytes were checked and removed. Source, linker, pinned model, execution logs, rebuild commands, and original input hashes remain. Owned containers for those runs are all removed.
