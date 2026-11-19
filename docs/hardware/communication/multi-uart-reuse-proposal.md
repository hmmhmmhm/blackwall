# UART instance reuse

Following task bw-0110 research, bw-0112 verified limited-function multi-UART execution. Full UART driver, boot, and display remain incomplete.

All three actual mains request UART2 power 800 after UART1 off. In the official DFP, UART1–3 inherit UART0's register layout. The pinned HAL also selects the same UARTn accesses and power/IRQ by module index. Rather than clone the existing engine specifically for UART2, separate only addresses, power bits, and IRQs for modules 0..3. This does not expand scope to a new complete UART driver or physical link.

| Module | Base | Power mask | IRQ |
| --- | --- | --- | --- |
| 0 | 40039000 | 200 | 15 |
| 1 | 4003a000 | 400 | 16 |
| 2 | 4003b000 | 800 | 17 |
| 3 | 4003c000 | 1000 | 18 |

Evidence: private multi-uart-research-01/source-report.json. These addresses/fields are source-supported; actual communication roles of each controller and compatibility with all firmware settings are not verified.

Pass module to one UART adapter/power implementation and connect only enabled instances to the fixture. The shared power bank's allowed mask is the sum of GPU/ADC and explicitly selected UARTs. Disabled instances and unknown bits are strictly blocked; count changes across all domains first, then change only one domain. Each instance owns separate register/FIFO/capture/IRQ/lifecycle state. Do not create cloned source or global shared UART state. Compare and regression-test existing UART1 behavior under the same profile.

NVIC route is 15+module and exception vector 31+module. Observation hooks record instruction execution and ICSR active vector at each original vector without changing code/PC. D2ASPARE clear also handles only bit 22+module and preserves other power settings. Do not automatically allow faster clock, DMA, external RX, or new serial protocols before actual main requests them and source evidence is confirmed.

Follow-up verification covers instance independence, invalid module, disabled addresses, atomic shared-bank rejection, IRQ routing, existing UART1 profile, and actual stock/CFW main with multiple UARTs. Common source layout alone does not complete full boot or CFW patch execution.

## bw-0112 implementation and verification progress

Configure common BlackwallUartAdapter/Power per module and retain them in one Uarts/UartPowers map in the fixture. Known execution callers migrated to the map API; the old UART1 class is not retained separately. Old type names in historical board fixtures are converted to the new type at the verifier input boundary. A complete tools search could not finish due to some iCloud read failures, so repository-wide migration verification is not claimed. Old source/fixture files are not deleted or rewritten.

Explicitly select enabled instances, e.g. `--uart-modules 1,2`. Apply the same selected profile to each instance and connect IRQ as 15+module. New CLI names uart-model/uart-interrupts/uart-off-response and retained uart1-* aliases for preserved commands use the same path. Disabled module bits/MMIO are blocked. If multiple D2ASPARE clear candidates exist, a restriction blocks rather than arbitrarily choosing one.

Standalone 117 and shared fixture 28 conditions were checked. Actual main with UART1/2 connected proceeded to a UART3 request after both UARTs completed off. Synthetic CPU per-instance IRQ and UART3 connection were then under investigation. Existing diagrams and synthetic guests do not substitute for full main execution or actual transfer success.

## bw-0112 final results

Final source unit 117, shared 28, synthetic IRQ 1/2/3 twice each, five actual main conditions, and snapshots were compared. Stock 2.4/2.3/Faceclaw each completed 26 writes and one off for UART1/2/3, then stopped at DEVPWREN 8. The corresponding official DFP bit is PWRENIOM2. Actual main TX/ISR were all 0 and full boot/display false. UART0 is within standalone module checks; do not expand this into successful actual main/CPU IRQ verification.

UART1-only profile observation fields matched previous results. Stuck-on retained UART1–3 status while progressing to the same IOM2 request, so it is not evidence of safe error handling. This compares source and extends module selection; PC, return address, and original main were unchanged. Stock 2.3/CFW assumptions are identical.

An error where the added host-source folder was made unreadable by the existing top-level chmod 0600 loop was fixed. Directories were separated as 0700 and top-level files as 0600, then final main 5 rerun. Shared checks also included PowerCycles for every module. Thirteen private runtime/verifier/fixture copies and a manifest were retained. This is not a complete repository backup or completed legacy migration audit.

Final evidence: private multi-uart-verification-01/final-verification.json, source-manifest.json, independent-review.txt, trail-audit.json. Independent review used a same-GPT-6-family fallback and raised no further significant issues. Follow-up is actual IOM2 initialization/transfer path and original CFW patch execution coverage research.
