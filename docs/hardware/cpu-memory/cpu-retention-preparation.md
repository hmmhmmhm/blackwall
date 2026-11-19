# Original Retention Preparation, WFI, and App Events After Reset

bw-0417. **After a virtual reset during execution, original stock 2.4 reinitialized services and reprocessed an ATT time message from a new virtual connection, updating RTC.** Original main, branches, WFI, return values, and PC/SP were not modified. Original code continued executing while only necessary peripheral contracts were extended.

E06 was not fully complete. The native target here was stock 2.4; the same reset scenario and state-lifetime verification for other originals remained. Overall acceptance remained 8/16 = 50.0%, first-display checklist 3/6. This does not prove normal GAF calculation, integrated display, or unlimited operation of the whole app.

## Actual execution path

Resumed from the pinned [previous retention configuration](cpu-retention-staging-contract.md) input, removing only the owned callback observing original return. Stage inputs and stop artifacts were preserved.

| Native artifact | Result |
| --- | --- |
| 01 | Unchanged model stopped strictly at TIMER1 CTRL `0x40008220` read, PC `0x5c1d02`. |
| 02 | Connected inactive TIMER configuration reads and traversed 13 channels. Stopped at AUDSSPWRSTATUS `0x40021010` read. |
| 03 | Connected explicit inactive-audio status read. Stopped at SYNC_READ `0x47ff0000` with SCR=4, CPDLP=`0x22`. |
| 04 | Connected retention flush conditions; original reached `0x44e176` after WFI. There was no sleep edge, so this is not evidence of actual waiting. |
| 05 | Returned to original sleep caller `0x4765e2`, restored CPDLP 0, guard/fault 0. A pending interrupt remained. |
| 06 | Subsequent execution confirmed M55 deep-sleep entry/exit and IRQ32, service reinitialization, a new connection, and RTC update by the original app. |

Reinitialization in 06 pauses normally at getter entry, the same existing observation boundary. This does not mean unsupported sensor behavior completed. At that boundary, virtual controller/phone input was supplied and the original SPI/HCI/ATT/TPL, task, and RTC path was reexecuted. There was no API test caller or task/TCB seeding.

At the subsequent service boundary there were 59 controller commands and zero events; after handling the new connection there was one event, and after new app behavior three. The actual app consumer returned at `0x492ce2`; RTC commits were 1 and date `2023-11-14T22:13:20.03`. All strict guards, architectural faults, and memory violations were 0.

## Required peripheral contracts

### TIMER state traversal

Original power-management code examines CTRL EN and clock fields for channels 0..15. Referenced channel addresses/reset 0 in the [pinned TIMER HAL](https://github.com/zephyrproject-rtos/hal_ambiq/blob/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/am_hal_timer.c) and existing verified SVD, and the unchanged shared timer engine.

Optional `idleChannelControls` reads only CTRL for inactive channels in the existing engine. Channels 0, 7, and 14 retain their existing state owners. The other 13 channels were each read once; selected channel values `0x120/0x42/0xa10` were preserved. Writes, starts, counter access, unaligned and partial-width access to inactive channels were not newly allowed. Default is false.

### Inactive audio status

SVD defines reset 0 for AUDSSPWREN `0x4002100c` and AUDSSPWRSTATUS `0x40021010`. The current board blocks all audio power-on and status writes as unsupported. Optional `inactiveAudioStatus` permits only reading status 0 of that explicit inactive profile. Audio engine, mic, clock, and ADC behavior were not implemented. The default board continues to reject that read.

### Retention flush

In deep-sleep preparation, original code sets SCR SLEEPDEEP and branches to the `0x44e16e` flush shared with normal sleep. Do not judge this path with the old normal-only CPDLP `0x11` and CPUPWRCTRL read-count conditions.

Optional `retentionFlush` checks actual guest context, pinned flush PC/R0, CPDLP `0x22`, SCR deep bit, and a new retention stage. Deep-flush count is recorded separately to avoid contaminating existing normal-cycle control-read/flush counters. Normal writes and reset rules remain. This uses the same synchronous APB fixture as before, not physical bus latency or implementation of every SoC power domain. WFI is left to original Renode execution.

`retention_preparation_models.py` applies extensions only to target classes. The common default core, TIMER adapter, and timer engine originals were unchanged.

## Scope of actual sleep observation

The first WFI completed with `MaskedInterruptPresent=true` and no sleep edge, consistent with immediate completion of WFI when an interrupt is pending. That point alone does not establish sleep/wake.

Continued execution in 06 contains this complete prefix:

- Deep-sleep high: virtual 14,327,100,000 ns, PC `0x44e176`.
- Deep-sleep low: virtual 14,348,305,800 ns, same PC. **Renode WFI wait: 21.2058 ms**.
- Then entry into original vector's STIMER IRQ32 handler `0x458812`. Observed xPSR exception number was 48 (16+32).

The signal comes from the pinned NVIC's actual WFI-state callback, using [GPIO's owned state-observation hook](https://github.com/renode/renode-infrastructure/blob/cd4b002aac2398994c4a61a34a8b31b5700facf2/src/Emulator/Main/Core/GPIO.cs). IRQ wiring was not replaced and the host did not inject a wake IRQ. This is not verification of physical G2 voltage, power consumption, retention accuracy, or measured time. It does not claim complete causal proof of the direct wake source or observer noninterference.

The 128-entry event buffer overflowed from later periodic IRQ records. Verify only the preserved prefix containing the first complete sleep cycle and subsequent IRQ32. Do not treat the entire IRQ history or all sleep cycles as complete.

## Checks and reproduction

Saved audits covered six native artifacts. For each run, distinguish 26 initial-configuration checks from subsequent 13/15/16/15/17/22 checks. Final unit 89 checked 13 inactive-channel read/write rejection, preservation of selected channels, audio default/inactive/write rejection, normal-flush regression, and reset. Earlier unit results of 76 and 84 were also preserved.

Rejected five counterexamples consistently reflected in JSON and logs: missing channel read, unexpected MMIO, lost RTC commit, zero-time sleep, and different ISR PC. Fourteen progress-management checks passed too. Frozen audit and regenerated-input comparison results are in the private manifest.

Source metadata for 03 lacks the audio flag, and synthetic diagnostics for 04 lack the audio read count. Audit against the executed board/model and actual next PC; do not invent missing values. The producer's diagnostic combination and metadata were subsequently fixed. Original inputs and execution results remain.

```sh
python3 tools/verify_retention_preparation.py <simulator-root> <existing-capture> <new-audit>
```

New native tests use explicit profile flags in `probe_cpu_retention_preparation.py`. Firmware, SRAM, NOR, and original logs are preserved in private `simulator/cpu-retention-preparation-native-01..06`, `timer-idle-controls-unit-01..03`, and `cpu-retention-preparation-research-01/manifest.json`.

There was no physical access, flash, OTA, Astra/subagent, or external publication. Next verify the same reset scenario by version, reset lifetime/retention policies, and observation coverage. Do not extend this stock 2.4 scenario success into completion of the whole emulator or E06.
