# TIMER0 Configuration Contract After Role Selection

Work bw-0215. The next `0x40008200` read after [GPIO role execution](gpio-role-input-model.md) was analyzed. The original stopped while about to clear existing TIMER0 enable and apply UPCOUNT configuration. It shares a register block with TIMER14 but differs from modes supported by the current adapter.

## Confirmed request

`inspect_timer0_sync_contract.py` compared actual pause registers/stack, reports, derived assets, and pinned main from six prior low/high runs of stock 2.4, 2.3, and Faceclaw38. It checked 118 items including HAL, SVD/CMSIS, common-engine pins, and register-offset compilation. No new main run or model change occurred.

| Item | Value confirmed in original |
| --- | --- |
| Module | 0 |
| CTRL0 | `0x120`: clock selector 1 (HFRC/16), function 2 (UPCOUNT), enable 0 |
| MODE0 | `0x100`: trigger source 1, CTRL trigger mode disabled |
| CMP0 / CMP1 | 6000 / `0xffffffff` |
| Interrupt mask | compare0 bit 0 |
| NVIC | IRQ67, priority 4 |

TIMER register base is `0x40008000`. CTRL0/TIMER0/CMP0/CMP1/MODE0 offsets are `0x200/204/208/20c/210` respectively. Ten register offsets were also checked with C `_Static_assert` targeting Cortex-M55.

The original config function proceeds in order:

1. Read CTRL0 and clear EN. The current block is this first read.
2. Write CTRL0=`0x120`, MODE0=`0x100`, CMP0=6000, CMP1=`0xffffffff`.
3. Set CLR to clear the counter.
4. Caller performs EN clear and CLR set/clear on the `clear_stop` path and requests compare0 interrupt mask 1.
5. Set NVIC67 priority 4 and enable, and enable global interrupts.
6. Finally call a separate timer-disable function, leaving initial configuration stopped.

Therefore **configuration/IRQ enable is not interpreted as immediate timer-counter execution**. Actual start calls and ISR behavior must be observed in later execution. Do not omit enable/clear during configuration or arbitrarily change compare values.

## Original IRQ path

IRQ67 vectors and initial ISR instructions were checked in all three mains. The ISR passes argument 0 and a stack output pointer to HAL reading common timer status, passes returned status to a clear function, then performs a subsequent call. This is not yet a test executing the ISR or injecting an IRQ. Success of subsequent callback/transport modules is unverified.

TIMER0 and TIMER14 share **GLOBEN, INTEN, INTSTAT, INTCLR, and INTSET**. Duplicating the existing model as independent per-module engines could split common status, mask, and clear semantics. One engine owning shared state with distinct per-channel adapters/IRQs is appropriate.

## Existing engine reuse candidate and limits

Current `BlackwallTimer14` is limited to nominal LFRC/XT, function 1, maximum CMP0, and other restrictions. TIMER0 HFRC/16, function 2, CMP0=6000, MODE0=`0x100` cannot be supported by merely renaming or removing existing guards.

Underlying `BlackwallApolloTimerEngine`, transformed from the pinned Apollo4 engine, already has 16 channels and individual IRQs. It includes an UPCOUNT case. However, its internal `OneShot` flag actually reloads **Value=0** after compare and does not disable enable. Describing it as stop-on-compare based only on its name would be wrong. This confirms upstream engine behavior, not all Apollo510 repetition/LMT semantics.

Clock selector 1 was confirmed as HFRC/16. The newly read [pinned Apollo510 clock header](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu/am_hal_clkgen.h) includes system MAX96MHz and HP250MHz macros. File contents were checked against pinned tree blob `deed0f50cfd471b58cac5eb3e82165a492105a6b`. **Those macros alone do not establish that the actual TIMER HFRC path is 96 MHz.**

The engine's current HFRC=96 MHz is a nominal scenario candidate; under that condition HFRC/16 is 6 MHz and 6000 ticks are 1 ms. This is not a physical measurement or period measured in this run. A new adapter must explicitly state clock assumptions and UPCOUNT reload/IRQ semantics and verify them through actual behavior tests. Storing MODE's disabled trigger source is distinct from supporting actual triggers.

## Verification conditions for next implementation

- Retain shared TIMER0/14 registers and per-channel pending/enable/clear under one owner.
- Preserve the default unsupported TIMER0 boundary and existing TIMER14 behavior.
- Accept source-required stopped configuration, CLR toggle, compare values, and disabled trigger configuration.
- Test enable/disable, counter, compare event, IRQ67, clear, and reactivation under nominal clock, distinct from physical timing.
- Do not silently allow unknown clock/function/trigger/output use.
- In original main check setup return, actual start/ISR reachability, and next unimplemented access. Do not force returns, branches, or IRQs to succeed.

## Evidence and overall state

Follow-up bw-0216 implemented the [shared TIMER0 profile](timer0-shared-engine-model.md). It confirmed local nominal counter/IRQ and stopped setup 0 for three originals in low/high modes; original ISR and silicon timing remain unverified. Unimplemented statements below describe the end of this contract analysis.

Results are outside Git in `simulator/timer0-sync-contract-03/report.json`, with compile log/object in the same folder. New clock header provenance, SHA-256, and Git blob are in `timer0-clock-research-01/sources.json`. Python compilation passed.

This stage analyzes source contracts and reuse conditions. TIMER0 model, period, ISR, full boot, BLE, display, and real-device installation/recovery were incomplete at that point. Product fulfillment remains 13/29 (44.8%); no glasses access, permanent writes, or external publication occurred.
