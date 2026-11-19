# Shared TIMER0 and TIMER14 Engine Profile

Work bw-0216. An explicit nominal TIMER0 profile was connected to the existing TIMER14 engine under the [TIMER0 contract](timer0-sync-start-contract.md). In the final model, six low/high runs of stock 2.4, 2.3, and Faceclaw38 returned 0 from original config/setup and stopped at the next XIP read. TIMER0 was stopped as source predicted; original ISR remains unreached.

## Shared state and supported scope

One instance/engine of existing `BlackwallTimer14` was retained, adding optional `timer0Profile="nominal-hfrc96-upcount"`. Default is none and the existing TIMER14 nominal XT/LFRC profile remains. No separate TIMER0 engine was created.

- TIMER0 registers are offsets `0x200..0x210`; TIMER14 remains `0x3c0..0x3d0`.
- The same engine owns GLOBEN and IRQ enable/status/clear/set, distinguishing TIMER0 bits 0/1 from TIMER14 bits 28/29.
- TIMER0IRQ connects to NVIC67; existing IRQ connects to NVIC81.
- TIMER0 CTRL supports only 0 or `0x120..0x123`, limited to confirmed HFRC/16, UPCOUNT, non-inverted, disabled trigger, and LMT0.
- CMP0 may store 0/6000, CMP1 0/`0xffffffff`, MODE0 0/`0x100`. Starting requires 6000/`0xffffffff`/`0x100`. Storing MODE does not support actual trigger behavior.
- Held CLR keeps counter 0; counter writes while running and configuration changes outside scope are rejected. Other channels, clocks, functions, and triggers are not automatically allowed.

The profile is a **virtual scenario explicitly assuming HFRC 96 MHz**. Model frequency at selector 1 is 6 MHz. Actual silicon HFRC, gating, error, output pulses, and full LMT semantics were not verified. Existing engine UPCOUNT reload behavior is used without claiming physical timing or cycle accuracy.

## GLOBEN reactivation defect and correction

Review produced a counterexample showing CTRL EN checks alone were insufficient: valid execution → stop with GLOBEN → change CMP0/CMP1/MODE to an unsupported running configuration → reactivate GLOBEN was possible. `timer0-shared-global-red-01/renode.log` reproduced failure accepting a bad-primary resume.

The same configuration predicate is now checked at CTRL EN and GLOBEN. TIMER0 and 14 that the new GLOBEN word would activate are **both checked before writing to the engine**. If one channel is invalid, neither the shared word nor the other channel changes partially. The same potential path for existing TIMER14 was strengthened. CLR-held/EN0 channels are not starting and are checked on later CTRL EN.

Added tests create invalid CMP0/CMP1/MODE while globally gated, then confirm resume rejection, full-state invariance, and resumption after configuration repair. TIMER14 CMP0/CMP1 were checked similarly. Normal start/disable/global-gate/clear semantics were unchanged.

## Local verification

The 34 items in `verify_timer0_shared.py` use a synthetic spin guest and Renode virtual time to confirm:

- Source config/held clear and 1500 ticks in 250 µs at nominal 6 MHz.
- Reload after compare, masked pending, IRQ67 pending, and W1C.
- Simultaneous TIMER0/14 pending and independent clear, shared enable/global gate/reset.
- Existing TIMER14 nominal LFRC counter.
- Rejection of unknown clock/function/trigger/period, other channels/IRQs, byte/status writes.
- GLOBEN counterexample and reactivation after repair.

Compare boundaries use margin under the existing engine's fractional-residue policy. These tests confirm NVIC pending/peripheral IRQ, not original ISR execution. Separate existing TIMER14 27 items also passed, 61 total.

Results: outside Git in `timer0-shared-unit-03`, `timer0-timer14-regression-02`. Constructor rejection before profile addition is preserved in `timer0-shared-red-01`.

## Original main execution

Helper `--timer0-profile` defaults to unknown and requires an explicit GPIO role scenario. When selected, it adds observation points only at source-118 contract config/setup returns and original vector ISR entry. Guest PC, return values, branches, and IRQ success are not forced.

Final results are preserved in `timer0-shared-main-02/`. Initial `main-01` used the model before the GLOBEN fix, so it was excluded from final evidence and all seven cases rerun with the corrected model.

| Input | Low/high config and setup returns | Next PC | Next block |
| --- | --- | --- | --- |
| Stock 2.4 | 0 / 0 each | `0x47605a` | XIP `0x80100000` read |
| Stock 2.3 | 0 / 0 each | `0x47132c` | Same |
| Faceclaw38 | 0 / 0 each | `0x47132c` | Same |
| stock24-default | Not reached | Existing `0x47d3f0` | TIMER0 CTRL0 read |

All six normal cases had CTRL=`0x120`, MODE=`0x100`, CMP0=6000, CMP1=`0xffffffff`, counter 0, running false, IRQ enable 1/status 0. Original ISR entry hits were 0. Thus **stopped setup succeeded; actual start/original ISR success is unconfirmed**.

The previous complete event prefix matched with drop 0. Default unsupported execution exactly matched prior board bytes, full CPU state, and observations. The 127 items in `verify_timer0_shared_evidence.py` compared actual logs/reports, current model, pinned main/derived assets, 61 local items, returns/state, and next boundary. One CLI prerequisite and Python compilation also passed. Results are `timer0-shared-verification-01/report.json`.

A review agent inheriting the parent model identified the GLOBEN issue and re-reviewed that pre-write checks for both channels and counterexample tests resolved it after correction. No additional significant issue was found. Astra was not used.

## Next boundary and overall state

Next analyze which NOR data and consumer format XIP `0x80100000` requires. Unverified XIP bytes were not supplied as 0/FF or otherwise. This stage does not complete stock assets, synchronization transport, full main boot, BLE, or display.

Product fulfillment is 13/29 (44.8%). Real-device installation/recovery remains incomplete; no glasses access, permanent writes, or external publication occurred.
