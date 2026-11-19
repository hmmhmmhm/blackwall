# UART clock selection and MEMLDO during original boot

Status: bw529 in progress. Original boot→main→display remains incomplete.

After UART1 on and CR 8, the original writes 0 to D2ASPARE (0x400201b0). This clears UART1PLL bit 23 in the shared word; existing MEMLDOREF field is 0. Actual boot did not execute the previous main-specific two-stage memory LDO configuration.

The low-baud path in pinned `uart1-research-01/am_hal_uart.c:1240–1270` clears only UARTnPLL bit. With no basis to require completion of independent MEMLDOREF configuration, only the MEMLDO condition in UART clock-spare candidate selection was removed. UART on, CR 8, preservation of other bits in the word, single candidate, and once-per-epoch conditions remain.

## Verification

- `private:simulator/boot-uart-clock-source-bw529-01/source-proof.json`: pinned source SHA and evidence of one expression change.
- `private:simulator/boot-uart-clock-cold-red-bw529-01/report.json`: previous model blocked a valid cold clock clear.
- `private:simulator/boot-uart-clock-cold-green-bw529-02/report.json`: 26 checks passed across four UARTs.

The first candidate test failed trying to read a private internal model epoch field. Current checks verify external behavior through public clear count and rejection of a second write. No additional model change was made to pass it.

Two attempts to reuse an old shared-bank fixture failed before execution due to references to a retired adapter type and Uart1Power field name respectively. Logs remain in legacy-regression-bw529-01/02 and are not counted as passing evidence. Instead of repeatedly correcting that old fixture, the current verify_uart1_adapter.py DRIVER checks shared-word preservation and existing behavior. These are distinguished from runtime/original firmware failures.

## Original execution result

All 117 current adapter regression checks passed. The corrected candidate executed 13,796,407 actual original instructions and stopped at PC 41c05c on shared-power request 40021004=8. Code/system protection and CFSR/HFSR errors were 0; main/frame were not reached. The request target is to be confirmed in follow-up using saved before/proposed/XOR and IOM mask. Authoritative record: `private:simulator/original-boot-uart-clock-native-bw529-01/frontier-proof.json`.

An identical 149773-byte boot dump was checked and cleaned up, and owned Docker removal confirmed for all seven runs. Source, logs, model, analysis, and reproduction commands remain.
