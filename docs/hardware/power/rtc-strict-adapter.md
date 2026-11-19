# Strict RTC Adapter

bw-0130. An optional MMIO model addressing differences identified in the [RTC reuse investigation](rtc-module-contract.md). It does not replace original firmware functions, PC, instructions, or guest RAM, or force successful branches.

## Implementation and assumptions

`rtc_engine_source.py` verifies the hash of pinned MIT Apollo4 RTC source. It changes class name/import scope and one machine wall-clock mode-change subscription only. `renode-rtc.cs` wraps it and handles the following. After original engine reset, the explicit virtual epoch is reapplied; host real time is not followed.

- The profile is a virtual 100 Hz counter starting at 2000-01-01 00:00:00. It is not verified actual oscillator/OSEL selection, power, silicon revision, or physical clock stabilization.
- Only ten known 32-bit offsets are handled. Byte/word/quad, reserved fields, and unsupported behavior strictly stop. INTCLR/INTSET reads and direct status writes are currently unsupported.
- Counter uses 2000–2099 and Apollo510 SVD century encoding. Subsequent MMIO outside the range is rejected; ERR129 or actual century rollover is not claimed implemented.
- LOW read saves an upper snapshot and UP read consumes it. Virtual elapsed time of at least 10 ms adds CTERR. This assumes upper is preserved even for late reads; detailed physical silicon CDC behavior is unverified. UP-first counter reads are unsupported.
- Counter writes are unsupported by default. Only explicit `hal-low-upper` checks WRTC, BCD, date, weekday, and source field and stages LOW. A valid UP commits synchronously with busy 1 before then. Invalid UP preserves pending state, and WRTC release with an incomplete write is rejected. This is a virtual transaction assumption following original/HAL path, not silicon fact resolving the SVD UP-first wording conflict. Actual write latency is not implemented.
- Alarm supports disabled or one-second repeat (RPT7) and valid BCD. Special 10 ms/100 ms alarms, other repeat modes, 24h disable, and CEB are unsupported. Zero ALMUP is allowed only as alarm-disabled initialization.
- IRQ2 connects to engine GPIO. Alarm/status and mask/clear functionality are verified in virtual time.

Startup fixture delegates 32-bit accesses through a small `IBlackwallRtc` interface and does not depend directly on engine implementation. Without the model the existing strict boundary remains. Select it with `--rtc-model epoch2000-100hz`. There is no need to add `--rtc-counter-writes hal-low-upper` before a write requirement is established.

## Isolated verification

Forty-four checks in `private:simulator/rtc-adapter-unit-03/report.json` passed, including leap day 23:59:59.99 → next day, 5 ms/20 ms split reads, stop/resume, staging and invalid-write atomicity, counter-write opt-in, software IRQ2, first alarm at 0.5 seconds and one-second repeats, reset, width, and unknown blocking. A new ARM spin guest and virtual time were used, distinct from original main tests.

unit01/02 failed from a fixture error querying the `@ none` object as a sysbus/root node. It was corrected to use the owner's `g.Rtc` reference. Guest code and RTC model were not adjusted to force success. Separate failed logs were preserved.

## Original execution verification

Five original runs in `private:simulator/rtc-functional-main-comparison-01/report.json` were checked:

| Run | Result PC | RTC read/write/commit |
| --- | --- | --- |
| Stock 2.4, write profile selected | 0x495f64 | 1/1/0 |
| Stock 2.3, write profile selected | 0x48a07c | 1/1/0 |
| Faceclaw38, write profile selected | 0x48a07c | 1/1/0 |
| Stock 2.4, counter writes unsupported | 0x495f64 | 1/1/0 |
| Stock 2.4, RTC model unused | Existing 0x507004 | Unsupported |

The first four passed RTCCTL read and RUN request store, stopping at MCUCTRL.CHIPPN (0x40020000) read. They are not evidence that counter read/write, alarm, or ISR paths executed in the original. Counter commits were 0, and the same endpoint was reached without enabling the protected write profile. Virtual time advanced after epoch, but is not claimed identical to actual device RTC time.

Stock 2.3 and CFW model, board, result, and probe match; run.py differs only in main length. Original raw hashes, memory policy, and actual logs/reports were checked. UART TX/ISR, I2C commands, and CQ pairs are 0. Without the model, the existing RTCCTL strict boundary and selected counter remain.

First original discovery failed report generation after CPU stop because RTC guard metadata was queried as a bus node. After correcting `guard_node` to use the owner reference, the five cases above were confirmed. That failure is not counted as a verified original execution result.

`rtc-adapter-cli-negative-01` confirms a request specifying only counter-write option is rejected before input/output/native. Source selection, CLI, reports, and failed material are preserved in the final verification directory. Independent GPT-6-family review found no additional significant issue; the parent separately compared the five original results. Astra, physical-device work, and separate transcript archive comparison were not used.

Next investigate the CHIPPN/SKU/CHIPREV information contract and actual original branches. SVD reset CHIPPN is 0x10320080, but is not assumed to be the actual device value. Full boot, integrated display, and installation verification remain incomplete; product conditions remain 13/29.

## Reproduction

Run isolated tests with `python3 tools/verify_rtc_adapter.py NEW_OUTPUT` and original comparison with `python3 tools/verify_rtc_main.py SIMULATOR_ROOT NEW_OUTPUT`. Existing private source, original bundles, and previous RTC selected-profile assets are required. Final source/log/hash comparison is preserved in `private:simulator/rtc-adapter-verification-01/report.json`.
