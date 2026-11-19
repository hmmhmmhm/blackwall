# UART TX event policy and resolution of repeated UART2 IRQ

Task `bw-0232`. An optional TX event policy was added to all four ports, including UART2. Stock 2.4, stock 2.3, and Faceclaw progressed past repeated IRQ to the next strict boundary in TIMER7 initialization. This is execution evidence within the model, not verification of actual Apollo510 IRQ timing.

## Evidence and scope

The TX IRQ in [Arm PL011 TRM DDI0183G §2.8.3](https://documentation-service.arm.com/static/5e8e36c2fd977155116a90b5) is based on FIFO state changes. It says enabling UART/IRQ alone before writing data does not produce a TX IRQ. The reviewed PDF is r1p5, PDF page 44/document 2-23. This principle was not assumed identical across all actual Apollo variants.

Pinned Renode `PL011.cs` has compatibility behavior setting a TX cause on UARTEN. Its reset bool-array `Array.ForEach(..., value => value=false)` also does not change the elements. Initial raw TX20 was observed in a native red test. An optional policy combining both behaviors was tested against SVD IES reset 0 and original restore order. Neither behavior is identified as the sole cause.

Six standalone original ISR tests confirmed return without clear/dispatch when ready=0, and reaching the UART2 handler call boundary when ready=1. Addresses are 20002b7c for 2.4 and 20000e8c for 2.3/CFW. Ready=1 tests are instruction fragments ending before dispatch, not evidence of complete ISR execution. This byte is not claimed to have been directly read in actual capture. Related pins, addresses, and TRM sources are in private `uart-enable-compatibility-01/source-report.json`.

## Implementation

Adapter `txInterruptQuirks` defaults true, retaining existing behavior. False applies the following:

- Clear engine raw causes after reset/powerdown to restore source reset state.
- Suppress only TX20 newly produced by the enable callback on UARTEN 0→1 when no TX cause existed before.
- Preserve actual byte transmission, FIFO changes, existing pending TX, separate TX complete, and DMA causes.

The adapter uses the existing engine's interrupt-clear API internally to remove the compatibility cause. It does not use an external tool during execution to clear NVIC pending or move CPU out of ISR. Original ROM, PC, branches, and returns were unchanged. Actual FIFO transmission time, bus contention, and Apollo-specific IRQ characteristics remain assumptions.

## Original execution comparison

An initial stock 2.4 experiment applying false only to UART2 eliminated repetition and delivered the eighth UART0 packet. Next, all four ports were consistently configured false.

| Input | UART0 transfers / completion IRQs | New native strict stop |
| --- | --- | --- |
| Stock 2.4 | 8 / 8, 289 bytes | PC 47d3f0, word read 400082e0 |
| Stock 2.3 | 8 / 8, 285 bytes | PC 4786c4, same read |
| Faceclaw | 8 / 8, 285 bytes | PC 4786c4, same read |

That address is CTRL7 in the pinned TIMER SVD. This capture reached a guard and the CPU stopped itself, rather than stopping at a host time limit. Active vector 0, zero UART2 exception entries, and all UART IRQ outputs low were confirmed. The first seven transfer bytes remain unchanged for each input, and the eight new stock 2.3/CFW transfers are byte-identical to each other.

Default true control retained previous UART2 repetition and seven transfers. This was a 45-second host observation, so only declared packet/IRQ/event invariants were compared. Exact CPU, instruction-count, or time identity is not claimed. The common runner rejects a bounded control without explicit comparison conditions.

## Path differences and remaining uncertainty

Stock 2.4 matches the existing observation prefix. Stock 2.3 added 92 initial storage events and CFW added 66 in the middle. No existing event was deleted or replaced; existing order remains a subsequence. After the previous endpoint all three inputs add one UART wrapper return and five LittleFS read/status pairs.

The 92 events are read 30/status 46/WREN 8/WRDI 8; the 66 are read 23/status 33/WREN 5/WRDI 5. Their shape resembles the [earlier log flush investigation](../../archive/cfw-log-flush-interval.md), but **caller, success/failure, and precise scheduling cause of this added interval remain unverified**. It is not judged harmless or storage/full-execution equivalent. The model changed IRQ input, so trace differences were not hidden or source execution forced equal.

## Verification and reproduction

- Pre-enable TX cause in red-01 exposed a reset-related issue. Red-02 explicitly cleared existing TX and reproduced TX generated again by enable alone.
- Four-port unit 64 checks, default UART regression 117. Actual byte/FIFO/pending/complete preservation and reset policy were checked.
- One UART2-only causal main, three four-port mains, and one legacy bounded control. Native input, logs, runner copies, and component SHA are in `uart-tx-events-main-01/` and `uart-tx-events-main-02/`. One board-anchor preflight error was rejected before native execution.
- Final audit 77 checks is `uart-enable-irq-verification-01/report.json`; reproduce with `audit.py` in the same folder. Additional IO differences and unverified scope were also recorded in the report.

Tools: `verify_uart_enable_irq.py`, common `run_native_candidate.py`, `uart-tx-events-candidate.json`. Historical source/input were not retroactively changed to the current candidate. Next investigate a contract for reusing the existing timer engine for TIMER7 configuration, start/stop, and IRQ. Normal font-bank and integrated display prerequisites remain tracked. Physical device access, installation, recovery, normal boot, and display remain incomplete; overall 13/29, 44.8%.
