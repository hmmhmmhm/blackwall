# UART0 connection and HCPA shared-status profile

Task bw-0222. Following the [original power contract](../display-gpu/post-font-uart0-contract.md), the existing module 0 UART adapter was connected and an optional HCPA shared-status response added. This continues an existing diagnostic scenario without normal font assets; it is not evidence of normal stock boot, display, or physical UART communication.

## Model scope

No new UART implementation was made. The existing adapter is registered at base 40039000, IRQ 15, enable mask 200. Existing nominal 24 MHz PL011 assumptions and TX/IRQ implementation scope remain; RX/DMA are unimplemented.

Root option `uartHcpaStatus` defaults false. When true, all four UART adapters must be explicitly registered. Each UART enable request remains independent. A DEVPWRSTATUS read returns all four UART bits 1e00 if any existing logical UART status is on. Non-UART GPU/ADC/IOM/MSPI/OTP/CRYPTO status is composed as before.

This is a source-based **status response profile**, not a complete physical HCPA-domain model. Virtual response delay still completes at the first status read. Previous assumptions for per-port logical phase, MMIO access gate, and register reset after off remain. Actual shared power-domain register retention, clock, delay, and power were not verified. Unit verification used active-on/off-response profiles for all four ports.

## Original main results

All three originals use low-role conditions retaining missing-font-magic-only diagnosis. Source main, PC, branches, and function returns were unchanged.

| Input/profile | Original power enable return | UART wrapper/client return | Next strict access |
| --- | ---: | ---: | --- |
| Stock 2.4 + UART0 + HCPA | 0 | 0 / 0 | Write 1fd0 to 40039038, PC 5ae4a4 |
| Stock 2.3 + UART0 + HCPA | 0 | 0 / 0 | Same, PC 5add98 |
| Faceclaw + UART0 + HCPA | 0 | 0 / 0 | Same, PC 5add98 |
| Stock 2.4 + UART0, independent status | 4 | 0 / 0 | Same UART0 interrupt-mask boundary |
| Faceclaw + UART0, independent status | 4 | 0 / 0 | Same boundary |
| Stock 2.4, UART0/HCPA unselected control | Blocked before UART0 request | Not reached | Existing write 600 to 40021004 |

The independent-status control matters: the wrapper ignores power-enable failure, so reaching subsequent UART configuration alone cannot establish readiness success. Under HCPA the enable function actually returned 0, including original 5 µs equality poll; independent status returned 4 (timeout). Return values were not forcibly replaced.

UART0 was observed logically on with request 200/status 200, Control 319, and one clock-spare clear in each extended run. IRQ-mask write was rejected by guard, leaving mask 0/IRQ low/TX bytes 0 and no original UART0 IRQ exception entry. It was not allowed before determining mask 1fd0 meaning. No actual baud or successful data transfer is claimed.

## CFW storage path difference

With the new HCPA profile, the two stock versions retained identical existing observation event prefixes. **The complete CFW trace is not identical.** Excluding added UART observation points:

- The 2,903 events through filesystem app initialization return match.
- Existing CFW then has 92 storage events before GPIO role sampling: LittleFS read 30, status-poll 46, write-enable 8, write-disable 8.
- HCPA-profile CFW has 0 events in that interval.
- The 17 events from GPIO role sampling through timer/font manager match.
- CFW control adding only UART0 with independent status retained matches the entire existing prefix.

The difference thus appears alongside the HCPA response change. Which CFW/stock branch or timing condition determines extra storage activity was not yet established. Do not judge it harmless, storage equivalent, or completed CFW compatibility. Root-cause tracing was follow-up work. The report retains `cause_verified=false`, `whole_trace_equivalent=false`.

Follow-up bw223 confirmed [pending/retry state of stock log flush](../../archive/cfw-log-flush-interval.md), comparing original logger code and file-open frame, request 3/completion 0, failure 1/pending 1, and 680/5000 ticks. The underlying first flush failure and later retry success remain unconfirmed. The earlier unknown record and report are retained as bw222-era evidence.

## Verification and preservation

- TDD red: `uart-hcpa-red-01` failed the status 1e00 check after request 200; behavior still returned previous 200.
- Thirty HCPA unit checks and 30 independent-status controls covered turning off one port and the last port, resumption, reset, GPU-bit preservation, and incomplete-profile rejection. Power-ready/quiescent inputs were explicitly synthetic.
- Six final original-main cases and 112 file/original/log/profile/difference audit checks: `simulator/uart0-hcpa-verification-01/report.json`.
- Final execution inputs/logs are in `simulator/uart0-hcpa-main-02/`. The unselected control matches all CPU, instruction counts, and events of the prior font diagnostic. It also uses the missing-font diagnostic, not a normal font-bank environment.
- First `main-01/stock24` lost 99 events because a shared peripheral-poll observer was called 1,136 times. It was excluded from final evidence and original execution input retained. Without changing model or event limit, `main-02` reran observing only the UART wrapper power-enable return. No events were lost in final six cases.

Whole-model changes are limited to root default-false option, validation, profile field, and one UART-status composition line. The previous root was exactly restored and compared with frozen source prefix; remaining model bytes matched. Original binary and derived input hashes were checked before/after. No physical access or persistent write occurred.

## Tools and next sequence

`tools/probe_uart0_hcpa_main.py` requires explicit `--uart0 --hcpa-status` to enable the new profile; `--hcpa-status` alone is rejected. Specify `--case stock24|stock23|cfw` and a new output path. This tool continues the existing missing-font diagnostic and supplies no normal font data.

Current execution boundary is UART0 interrupt-mask 40039038/1fd0. Next determine HAL/SVD meaning and RX/DMA dependencies of that mask, and trace the CFW storage-interval difference. Actual font-bank, normal glyphs, app loop, and integrated framebuffer remain necessary. Overall progress for web-installable Faceclaw CFW, recovery boot, and integrated simulator remains 13/29, 44.8%.
