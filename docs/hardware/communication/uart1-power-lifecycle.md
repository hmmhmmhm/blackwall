# UART1 power-down and resume model

Tasks bw-0108/0109. This does not verify physical power or precise clock/reset timing.

The current three mains request UART1 power-down after clear-all→CR 0. Public HAL power_control stores ILPR/IBRD/FBRD/LCRH/CR/IFLS/IER/DCR in guest SRAM when retain=true, and uses clock release→clear-all→CR 0→peripheral disable order. On wake, the guest restores saved registers after peripheral enable. Do not assume actual main uses the entire same ABI; only the current MMIO order matched. UART1's communication role remains undetermined.

A separate opt-in `--uart1-off-response off|stuck-on` is added. It requires the UART IRQ model. Only quiescent requests with CR 0, raw interrupt 0, IRQ low, and DMA 0 are accepted. The request bit falls immediately and status bit falls on the first status read: an explicit digital assumption. Stuck-on retains status 400 and does not prove safe fallback after failure. Unselected retains the previous on→off block.

On successful off completion, virtual UART registers reset and IRQ/mask/TXCMP are lowered. TX capture and observation counters accumulate, with power-down count tracked separately. Subsequent explicit power enable responds on again. The original guest code must restore registers; the host does not do it instead. Shared D2ASPARE is preserved and only the UART1PLL clear epoch is reopened. TX/IRQ after initialization and restore also use only existing boundaries and source-supported behavior.

Simply allowing power requests and retaining registers forever was not adopted because it would hide guest restore errors. Always-off or on-only alternatives cannot verify lifecycle progress and remain only as separate failure profiles. Main code/PC/return address are not changed and no physical glasses are accessed.

`PowerCycles` / report `power_cycles` counts completed off operations, not round trips through reactivation. Raw TX20 can appear after PL011 reset, but mask is 0/IRQ low and powered-off MMIO is blocked. Actual guest wake/restore success must be separately observed in original main.

## Current verification results

Final source unit 89, shared fixture 23, synthetic IRQ 16 twice, five main conditions, and combined snapshot were checked. Stock 2.4/2.3/Faceclaw each requested DEVPWREN 800 (UART2) after one UART1 off and one register reset. GPU/ADC retained powered-off state. Actual main TX/ISR were 0 and wake/restore remains unconfirmed.

Stuck-on retained status 400/request 0 and zero resets, but progressed to the same UART2 request. Therefore no claim is made that original firmware handled the failure safely. The unselected profile blocks at the existing UART1 off 0 request. Missing CLI dependencies are rejected before input and output creation.

The first shared-fixture check failed attempting direct assignment to an internal setter. After correction to prepare via public MMIO, all 23 checks passed. The original failure log was retained. Evidence: private uart1-life-verification-01/final-verification.json and trail-audit.json. Subsequent multi-UART reuse plan and address evidence are in [multi-uart-reuse-proposal.md](multi-uart-reuse-proposal.md).
