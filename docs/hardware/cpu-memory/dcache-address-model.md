# SRAM Address-Based Cache Maintenance Model and Original Execution

Task `bw-0229`. Implemented optional `sramAddressMaintenance` in coherent D-cache according to the [original/CMSIS contract](dcache-address-contract.md). CPU PC, instructions, branches, and function returns were unchanged. No physical device was accessed.

This profile requires coherent D-cache and defaults to false. It handles 32-bit MVA invalidate/clean/clean-invalidate in SRAM `20000000..20380000`, ignoring the low five bits for line selection. Address commands do not satisfy set/way initialization conditions. The existing coherent-memory abstraction does not create separate dirty-data movement or cache latency. Unsupported boundaries for out-of-range addresses, widths, reads, and similar accesses remain.

## Integrated verification with original main

Used `run_native_candidate.py` and `sram-cache-candidate.json` to replace only the system-control component from an existing HCPA gate snapshot, with SHA before and after. Three originals executed from reset. Runtime changes were the SystemControl opt-in argument and diagnostics after stop; no new guest observation points were added. Input hashes, pinned image, original main, and candidate component list are in each execution's manifest.

| Input | Actual cache-maintenance result | Next strict boundary |
| --- | --- | --- |
| Stock 2.4 | One clean at SRAM `2035cc60` | PC `57f01c`, write `2035cc60` to UART0 TARGADDR `4003904c` |
| Stock 2.3 | One clean at SRAM `20377740` | PC `5a1af0`, write `20377740` to the same TARGADDR |
| Faceclaw | One clean at SRAM `20377740` | PC `5a1af0`, same access |
| Stock 2.4 option off | Zero cleans, previous system-control stop | Previous CPU, instruction count, events, and stop point all identical |

The three extended cases preserved the prior observation-event prefix. System-control and memory-policy violations were 0; execution stopped with one MMIO rejection at UART0 DMA destination configuration. UART0 TX bytes and IRQ exceptions were 0; DMA start/completion and peer response were not yet implemented or verified. This confirms the actual CPU → NVIC/system-control hook connection, addressing the gap in direct TryWrite unit tests.

## Verification and review response

- TDD red `dcache-address-red-01`: confirmed SRAM clean rejection.
- Unit `dcache-address-unit-01`: 51 checks covering address/width/range/default rejection, low-five-bit handling, counter separation, initialization of 2,048 set/way entries, and invalid profile combinations.
- After separating candidate assembly, the unit model was byte-identical, so the same native tests were not repeated. Reuse rationale is in `astra-direction-review-01/report.json`.
- Six existing cache regressions: full sweep, clean/invalidate, missing sweep, byte command, read command, and default strict; `dcache-address-regression-01/report.json`.
- Four original-main cases: `dcache-address-main-01/{stock24,stock23,cfw,stock24-default}`.
- Final 54-check audit: `dcache-address-verification-01/report.json`, reproducible with `audit.py`. Includes source contract, original/model/inputs, prefix, actual clean, new boundary, and rejection of ambiguous reports, host timeout, memory violations, and similar conditions.

The initial change connecting current system-control to the global model builder broke historical audits and was reverted according to the [Astra review](../../project/astra-direction-review.md). Candidate assembly was separated into explicit helper/plan, and four historical HCPA main cases were re-audited without input/log changes or native reruns. The existing 53-check HCPA audit was also restored. Do not retroactively apply the current candidate as a baseline for historical evidence.

Next proceed by the unit described in [UART0 transfer flow and display prerequisites](../../architecture/simulator-next-behavior-plan.md). Normal font bank, full boot, integrated display, and actual installation/recovery remain incomplete; overall criteria were 13/29, 44.8%.
