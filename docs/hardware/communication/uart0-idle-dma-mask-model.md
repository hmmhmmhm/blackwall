# UART0 interrupt mask with DMA idle

Task `bw-0225`. Following the [source contract](uart0-interrupt-mask-contract.md), limited storage of UART0 DMA interrupt masks was added. Original ARM code was not modified and no branch, function return, or wait was bypassed. No physical device was accessed.

## Implementation scope

`BlackwallUartAdapter`'s `idleDmaInterrupts` defaults to false. True is allowed only for module 0 with interrupts=true. That profile stores the 13 defined IER bits (1fff). Only the existing lower mask 7fe is passed to existing PL011; DMA raw state is 0 under a reset-idle assumption. The upper DMA mask is not allowed when DCR is nonzero.

Starting DMA and changing priority are unsupported. Nonzero DCR writes and RX data reads remain rejected. The existing 7ff restriction and IRQ/TX behavior remain for all UARTs without the profile. This is not a DMA implementation or verification of physical power/receive state.

## Original execution results

The existing `uart0-hcpa-main-02` missing-font-magic-only and HCPA response profiles were retained. No new code observation points were added; run.py/result.py, original main, and initial memory were unchanged. Bytes outside allowed model changes and the board's one opt-in line were compared.

| Input | Previous strict boundary | New strict boundary |
| --- | --- | --- |
| Stock 2.4 | PC 5ae4a4, 1fd0 to IER 40039038 | PC 494d78, 600 to power 40021004 |
| Stock 2.3 | PC 5add98, same IER | PC 488e90, same power write |
| Faceclaw | PC 5add98, same IER | PC 488e90, same power write |
| Stock 2.4 default-profile control | PC 5ae4a4 | Identical to all previous CPU, instruction count, and events |

The existing observation event prefix matches across all three extended runs. UART0 mask 1fd0 was stored once, Control 0, IRQ low, UART0 exceptions 0, TX bytes 0. The original then requested off and the model is in `off-requested`/RequestWord 0/StatusWord 200. The next enable write 600 is rejected. This is not interpreted as DMA receive/transmit or reaching a normal app loop.

Next analyze **UART0 shutdown/restart while the shared HCPA domain remains on**. The existing model completes the off response only on status read. Before changing the model, verify whether the original restarts without reading status and how that relates to the HAL shared-domain reference management. Do not add immediate off success, register reset, or restart permission based on this stop alone.

## Verification and reproduction

- TDD red: native `source-reset-DMA-idle-mask-accepted` failed in `uart0-idle-dma-mask-red-01`, confirming mask rejection before model implementation.
- Unit `uart0-idle-dma-mask-unit-02`: 33 checks covering mask readback, DMA control reset, unsupported RX, rejection of DMA start/reserved bits/power off, reset/powerdown, default four-port restriction, and invalid profile rejection. Unit-01 had 30 checks before three additions including readback.
- Regression `uart0-idle-dma-uart-regression-01`: 117 checks running the existing UART adapter DRIVER against the current complete model and pinned Renode image.
- Four original main runs: `uart0-idle-dma-main-01/{stock24,stock23,cfw,stock24-default}`. Input hashes were checked before and after execution.
- Final audit `uart0-idle-dma-verification-01/report.json`: 48 checks covering model change scope, original main, existing prefix, default behavior, new boundary, and limits on completion claims.

All results are retained outside Git in `simulator/`. Reproduction tools: `tools/verify_uart0_idle_dma_mask.py`, `tools/probe_uart0_idle_dma_main.py`, `tools/verify_uart0_idle_dma_evidence.py`. The main tool's `--default-control` checks exact previous behavior without opt-in. Use only a new output path.

Normal external font-bank, full boot (S6), integrated BLE (S5), integrated display (D3), and actual installation/recovery remain incomplete. Product completion remains 13/29, 44.8%.
