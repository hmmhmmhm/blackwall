# PMIC Scratch Storage and Boot-Monitor Boundary

bw-0145. Initially investigated as unknown addresses, this was identified as the public ERRLOG region by comparing symbolic registers and base.

## Source contract

At base 0e00 in the [official ERRLOG map](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/ctrl_reg/doc/error_log.html-topic?contentId=lhuNtXJ4mIPOEu_NICgjZg), 0e02 is SCRATCH1 and 0e01 is SCRATCH0. Scratch is distinct from reset cause/error registers. errlog.c/h from pinned npmx `4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f` were checked against existing tree Git blobs and SHA-256 and preserved in private `npmx-errlog-research-01/sources.json`. Existing adc.c stores the NTC beta low byte in SCRATCH1 and upper seven bits in SCRATCH0. The errlog API first reads SCRATCH0, preserves bit 0, then changes the upper seven bits.

SCRATCH0 bit 0 controls boot-monitor, so it is not treated as an ordinary scratch byte. Upstream ADK POR comments and [reset documentation](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/reset/doc/frontpage.html?contentId=SPCgw7FE4EUHJL0w26Qk3Q) are not generalized to verification of physical restart. Error-clear tasks and physical POR/soft reset are outside model scope.

## Optional model

With `scratchState="guest-storage"`, SCRATCH1 is readable only after guest write. SCRATCH0 starts unknown. Writing bit 0=0 does not assume an unknown boot-monitor was disabled. Even writes make only the upper seven bits known, and the entire byte cannot be read until bit 0 is known. Writes with bit 0=1 are rejected because boot-monitor functionality is unimplemented. Status, reset causes, and error-clear tasks are unsupported.

Only runs explicitly specifying `scratch0InitialMock=0` supply initial SCRATCH0 00. It is not a value read from actual G2. This fixture is a mock condition for investigating RMW and does not change defaults. Value 1 and other seeds are rejected. Model Reset() initializes the declared fixture; it does not implement actual PMIC soft-reset scratch retention. Ordinary memory writes and scratch preservation are not interpreted as physical MRAM/nonvolatile data recovery.

## Verification

`pmic-scratch-unit-01` passed 344 checks: existing 310 and 34 new. They cover unknown/partial masks, readback, atomic rejection of boot-bit writes, task/status/burst blocking, copy return, Reset, and invalid seeds. Original execution is investigated in five cases retaining pinned main bytes and CPU policy. Three originals use explicit seed 0, the default control disables scratch, and a separate stock 2.4 control enables scratch without a seed. All five private `pmic-scratch-main-01` cases completed.

| Condition | Scratch values | Known masks | Writes | Next rejected request |
| --- | --- | --- | ---: | --- |
| Stock 2.4/2.3/Faceclaw, explicit seed 0 | [20,9a] | [ff,ff] | 2 | 050b read pointer, width 2 |
| Scratch-disabled control | [00,00] | [00,00] | 0 | 0e02 write, width 3 |
| Stock 2.4, scratch enabled, no seed | [00,9a] | [00,ff] | 1 | 0e01 read pointer, width 2 |

Bytes/masks in the table are hexadecimal. Internal value 0 for an unknown bit is not interpreted as actual 0. The new request address is identified by guard LastValue; LastAddress may be the previous pointer. Actual scratch history for the three original inputs was 0e02=9a, 0e01=20. The first 0e01 RMW read is explicit fixture 00. Interpreted with upstream API bit layout, this corresponds to beta 0x109a, but does not verify an actual thermistor or temperature. Existing charger-threshold storage writes also proceeded afterward. This is not full ADC initialization success.

The 100 checks in `pmic-scratch-verification-01/report.json` compared source/unit 344/main 5 raw results, exact bytes/known masks/history/next rejection cause, default boundary preservation, pinned main invariance and identical 2.3/CFW conditions, upstream SHA/blob, and latest timer/unit/feed sources. All execution inputs of seed-0/unknown stock 2.4 runs were byte-identical except the board's one scratch0InitialMock line. This makes the progress's dependence on the initial fixture assumption explicit.

After constructor extension, `pmic-timed-unit-08` 240 checks and `recovery-pmic-feed-09` five ARM cases were also reverified. The recovery function test remains under explicit power/pin/frozenDWT/status-hole mocks. Independent GPT-6-family review's known-mask/bootmonitor interpretation feedback was incorporated. No transcript archive comparison was performed. Boot-monitor, actual reset, full boot, and display remain unverified. Product numerator remains 13/29.
