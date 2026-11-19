# IOM4 Strict Model Integration

bw-0119 observes original main's IOM4 initialization requests. It does not complete DMA/CQ or physical-device functionality. No physical access, flash, or device RAM execution occurs.

## Model and virtual board

The same strict adapter as IOM2 was connected as an independent IOM4 instance, using power mask 0x20, base 0x40054000, IRQ10. The low power bank shares per-module power objects and changes only one domain after checking total changes. See previous `iom4-nonblocking-path.md` for source-supported layout.

Select with `--iom-modules 2,4`. Default remains 2; only selected 2/4 are allowed. Existing option `--iom2-model` is the base digital power response for selected instances; `--iom4-model` overrides only module 4's response. These are virtual fault scenarios, not actual power states.

Only selected `0x400`-byte ranges are separated from the guard; preceding, intervening, and following regions remain strict guards owned by the same owner. Selecting module 4 alone does not open IOM2's address range. Duplicate/unsupported modules and invalid power overrides are rejected. `observed.ioms` records each instance; existing `observed.iom2` is a compatibility field showing the same state as its list entry.

## Verification scope

- Standalone adapter 98 conditions reverified: `private:simulator/iom4-adapter-regression-01`.
- Shared bank/boundary 33 conditions: `iom4-shared-unit-01`. Checks include rejecting simultaneous changes in another domain, preserving IOM2 clock/config when IOM4 is off, per-instance power/reset separation, and blocking unselected module addresses.
- Synthetic IOM4 INTSET reached NVIC10 pending and cleared afterward; this is not CPU ISR execution.
- Existing UART adapter 117/shared 28 regressions were rechecked on new source after power-bank changes: `iom4-uart-regression-01`, `iom4-uart-shared-regression-01`.
- Pure board generation checked contiguous guard regions for (2), (4), (2,4), (4,2), and five invalid selections: `iom4-guard-geometry-01.json`. This alone does not replace runtime verification.

## Actual original main observations

The first stock 2.4 run `iom4-main-stock24-01` passed IOM2 initialization/off and enabled IOM4. It configured MI2CCFG=0x23040, CLKCFG=0x0b052101, SUBMODCTRL=0x30. Clock numbers are virtual register values, not a physical 1 MHz measurement. With IOM4 writes 4/reads 2, commands 0, it strictly stopped on CQSETCLEAR (0x40054238)=0x800040 write at PC 0x581848. There were no warnings.

This matches the previous static prediction for the NB enable branch. It requests SWFLAG6 set/7 clear; it is not CQ enable or successful DMA execution. No I2C peer was connected to actual main.

Final comparison covers stock 2.3/2.4/Faceclaw and independent IOM2/IOM4 power-failure conditions. A limited 32-byte SRAM observation was added for the stock24 handle based on r5=0x20040b28 in the first run. A 128-byte registration table and 32-byte NB-buffer prefix are also captured read-only. Other-version snapshots at the same address are not interpreted as stock24 state. Guest RAM and branches are unchanged.

The three active runs in final `private:simulator/iom4-main-comparison-01/report.json` stopped at the same CQSETCLEAR request. PC is 0x581848 for stock 2.4 and 0x57a4f0 for stock 2.3/Faceclaw38. Warnings: 0. In IOM2 failure, IOM4 was still off; when only IOM4 was failed, IOM2 remained fully off. Each failure blocked an unpowered FIFOTHR write request for that module. This does not establish the result of that write on actual hardware or safe firmware recovery.

Actual stock24 handle snapshot matched module 4, mode 1, NB pointer 0x203366e0, length 0x800. Combined with arithmetic in checked code, it supports an 8192-byte size calculation for this path, but does not prove actual allocation lifetime or DMA accessibility. A 32-byte buffer prefix does not verify all 8192 bytes.

`tools/verify_iom_evidence.py` compared 18 sources, combined C#, host source, raw logs/reports, main SHA/vector, stock 2.3↔CFW run.py identity except length, 36 DFP masks, standalone 98/shared 33/UART 117/shared 28. They are preserved in `private:simulator/iom4-verification-01/report.json` and source copies. Independent same-GPT-6-family review found no additional significant issue. Other model families and archived transcript comparison were not performed.

## Remaining work

CQ software flags, pause, address/data fetch, DMA trigger, and SRAM access contracts need analysis. Existing source-derived polling engine DMA/CQ placeholders are not treated as execution models. Model blocking on power-readiness failure does not establish safe firmware fallback. Full boot, integrated display, and physical installation remain incomplete; product progress remains 13/29.
