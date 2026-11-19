# HCPA UART port gate and shared power shutdown

Task `bw-0227`. Following the [original/HAL contract](uart0-hcpa-restart-contract.md), port shutdown/restart without a status poll was implemented. This simulated profile does not verify physical register retention, power, or latency.

## Optional lifecycle

Root `uartHcpaGate` defaults false and requires existing `uartHcpaStatus`. HCPA status requires four registered UART adapters. When another modeled UART is on with its mask in both request and status, removal of a quiescent port's enable under off-response 0 is represented as `gated`. Port registers are preserved; no physical domain off or PowerDown is fabricated.

If the same domain remains on, an enable re-request returns to local on. When the last user's actual simulated off response succeeds, PowerDown/reset is applied to gated ports too. If the off response is stuck-on, gated ports are not reset. If ready/quiescent/peer conditions are unmet or the off profile is unspecified, the existing boundary remains.

`BlackwallUartPower` owns this state. Only the parent peripheral-power state setter was opened as protected; non-UART derived behavior and default TryWrite were unchanged. Root computes peer state on request change and cleans up gated ports on last-user off completion. GPU/ADC/IOM/MSPI/OTP/CRYPTO power contracts remain unchanged.

## Original ARM execution

Stock 2.4, stock 2.3, and Faceclaw ran from reset under the existing missing-font diagnostic, HCPA, and UART0 idle-DMA-mask environment. No new code observation points were added. Original main, initial SRAM/ITCM, and run.py/result.py were identical; the board added only `uartHcpaGate: true`. Pre/post-review model core hashes and remaining frozen model bytes were compared.

All three retained the previous observed-event prefix and passed UART0 shutdown/restart and stored-setting restoration. UART0 requests/responses 2, off request 1, power cycles/PowerDown 0, CR 319, IER 1fd0 stored twice, TX bytes 0, UART0 IRQ exceptions 0. A stock 2.4 control with the feature off exactly matched all previous CPU, instruction count, and observed events.

| Input | Next PC | Access rejected by guard |
| --- | --- | --- |
| Stock 2.4 | 57f35c | Write 2035cc60 to e000ef68 |
| Stock 2.3 | 5a1e9e | Write 20377740 to e000ef68 |
| Faceclaw | 5a1e9e | Write 20377740 to e000ef68 |

This is an **unsupported stop** at a new cache-by-address management access. The unsupported system-control write was not executed and the guard was not disabled. CPU stopped with system-control violation 1, not an ordinary MMIO rejection. Existing `native_replay.parse_log` allows only MMIO guard 1/system violation 0, so it rejected the first stock 2.4 audit. Rather than hiding the actual execution failure, the saved input/log were retained and re-audited with a new typed boundary classification. The original was not rerun.

The new classification requires MMIO 0, memory violation 0, the exact e000ef68 word write, aligned SRAM address, identical PC, and CPU's own stop. It accepts no other system-control/memory error or host timeout. A report pass verifies the observation contract, not boot success.

## Evidence and reproduction

Execution, unit, and audit files are retained outside Git in `simulator/uart-hcpa-gate-*`. Tools: `tools/verify_uart_hcpa_gate.py`, `tools/probe_uart_hcpa_gate_main.py`, `tools/verify_uart_hcpa_gate_evidence.py`. Pass pre-review `renode-strict-mmio.cs` from source backup to main as `--baseline-core`. Check source SHA and current reviewed core SHA; use only a new output path. `--audit-existing` verifies terminal input/log and writes only a report.

TDD red failed as `shared-port-gated-without-poll` in the previous model, which could not represent a local gate. The first implementation unit-01 failed to compile due to a missing LINQ using, and was excluded and retained; corrected unit-02 passed 25 checks.

Final normal unit-03 passed 38 checks and stuck-unit-01 passed 37, including all four port gate/reopen, rejection of unspecified off and invalid profile combinations, and preservation on final off failure. Existing UART DRIVER 117 checks and HCPA status DRIVER 30 checks passed on the current complete model. Reproduce with `--regression uart|status`. Unit-test ready/quiescent/peer inputs are explicit simulated values.

All 53 final checks in `simulator/uart-hcpa-gate-verification-01/report.json` passed. They compared four original runs, input/model hashes, prefix, default behavior, and new system-control stop, and checked nine rejection conditions including memory error, incorrect system address/width/value/PC, and host timeout. These are not product boot or physical verification pass counts.

Next compare the original cache management function and address range for e000ef68 with the existing coherent D-cache model. DMA transfer, normal font-bank, full boot, integrated display, and device installation/recovery remain incomplete. Overall product completion remains 13/29, 44.8%.
