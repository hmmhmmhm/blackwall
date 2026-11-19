# Original Watchdog Request and Virtual Reset Connection Contract

bw-0424. Long-running original stock 2.4 ARM reaches a watchdog reset request before GAF timeout. This work **confirmed original configuration and an allowed gate**; it is not actual reset propagation or successful reboot. Original branches, polling count, watchdog configuration, and clock were unchanged.

## Values confirmed from saved execution

| Item | Observation |
| --- | --- |
| Watchdog CFG | `0x020ce005`: WDTEN=1, RESEN=1, INTEN=0, CLKSEL=2 |
| Reset threshold | 224 |
| CFG reads/writes | 5/3 |
| Restarts | 188 |
| RSTGEN CFG | 2, WDREN=true, one write |
| Gate evaluation on request | Performed, allowed |
| IRQ stage | Interrupt event 0, pending/IRQ=false |
| Stop reason | Explicit machine pause in watchdog timer callback |

Four full SRAM snapshots and existing frozen-core JSON match the earlier passive-pause observation run. Existing GAF busy 15,132, normal calculations 0, and no observed timeout return also match. The additional collector reads only public properties after final machine pause. This is not generalized into a guarantee that every observer has no effect.

## Time and reset meaning

The current WDT model assumes LFRC 1024 Hz. Its selected CLKSEL 2 counter is 16 Hz, giving a nominal 14-second interval at threshold 224. Since the last restart time was not collected, **actual observation of 14 seconds after the last restart cannot be claimed**. Physical clock calibration was also not performed. Board `PerformanceInMips: 10` declares a virtual instruction execution rate, not measured Apollo510B frequency. Neither this value nor the original loop is adjusted to reach timeout.

Current model `ResetDue=true` does not mean reboot completed. After gate evaluation it stops the timer and calls `PauseAndRequestEmulationPause`. That board does not yet use the existing verified reset-vector/NVIC profile. Existing SYSRESETREQ execution results cannot be reused as watchdog-reset results.

## Required conditions for next implementation

1. Reuse vector/SP re-entry, reset-aware NVIC, memory protection, and cache lifecycle verified in bw414–420 as an optional profile.
2. Check allowed/blocked watchdog request gate, single delivery, duplicate requests, and new watchdog configuration after reset. Do not arbitrarily reboot when blocked.
3. State reset-domain SRAM/NOR/RTC/ITCM and peripheral lifetimes. Do not generalize existing idle-reset verification to full active sensor/communications lifecycles.
4. Declare reset-cause delivery as a main-only virtual boot contract and compare with actual original-main consumption.

[Pinned Apollo510 CMSIS definitions](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/CMSIS/AmbiqMicro/Include/apollo510.h) distinguish WDREN as CFG bit 1, WDRSTAT as STAT bit 6, and AIRCRSTAT as bit 12. In particular, the STAT comment says boot ROM/secure bootloader retain or update status after reset. Thus setting STAT bit 6 in an emulator starting from main must be an **explicit virtual boot-delivery contract**, not claimed as full actual ROM/SBL execution or physical latch verification. Wording that reserved bits are writable is not used as grounds to generally allow status writes.

## Verification and limits

Twenty saved-material audits in `verify_watchdog_natural_request.py` passed. Three forgeries—disabled gate, physical clock verification, and completed reset implementation—were rejected under their respective conditions. After freezing the auditor and direct dependency sources, result JSON was byte-identical. Material is preserved outside Git in `watchdog-natural-request-native-01` and `watchdog-natural-request-research-01`.

E05 required initialization, the full E06 reset assessment, and E16 development tools remain incomplete; overall progress is **8/16=50.0%**. This audit does not complete acceptance conditions. No physical-device access, writes, subagents, or external publication occurred.
