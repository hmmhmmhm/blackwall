# UART1 clock selection and shared configuration preservation

Task bw-0104. Full boot, display, and physical verification remain incomplete.

All three actual main inputs wrote 10000 to MCUCTRL.D2ASPARE (400201b0) after UART CR0→8. Pinned HAL am_hal_uart.c:1262 clears the UART0PLL mask shifted by module at low baud. UART1 is bit 23 (mask 800000). The official DFP MCUCTRL base 40020000, D2ASPARE offset 1b0, and field were compared. MEMLDOREF[16:15] in the same word had been set to 10000 by earlier memory LDO configuration.

Only this initial path is connected. It requires UART1 power on, CR=8, and both memory LDO stages complete, and accepts only the existing shared word with bit 23 cleared. Other power/UART fields are preserved and it is allowed once per epoch. Storage uses the existing HAL backing word. PLL generation, physical gate, clock stabilization, repeated reset, and high-baud paths are not implemented. Material: private uart1-clock-research-01/source-report.json and pinned HAL in uart1-research-01.

## Current verification results

The final source was checked with 50 standalone checks (including 6 clock shared-word checks), 14 shared-bank checks, and five main conditions. Combined C# snapshots for standalone core and main/shared were compared against current eight source/runner/verifier hashes. Stock 2.4/2.3/Faceclaw each show one clear, 23 UART writes, CR 319, diagnostic baud 923076, and TX 0 bytes. The next strict stop is UART IER 4003a038=471 write. IRQ is not treated as simple storage; follow-up investigates HAL, firmware ISR, NVIC, and UART cause/clear behavior. UART1's actual role is not determined before output/protocol is verified.

Stuck-off showed zero configuration writes and one power block. With the option unselected, execution stopped at the existing UART power request. ADC/GPU in active3 retained powered-off state. Missing CLI dependencies were rejected before input reads or output directory creation. Firmware safety recovery from power failure is unverified. Final evidence: private uart1-clock-verification-01/final-verification.json.

Independent review used a same-GPT-6-family fallback; no separate transcript archive was provided. The initial baud-exception hypothesis was corrected by runtime observation, and fractional truncation correction and shared-bank checks incorporated. No further significant issues were raised. Full boot/display/physical/installability decisions are all false.
