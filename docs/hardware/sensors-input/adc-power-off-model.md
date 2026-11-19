# ADC Power-Off After Stop

Status: analysis of the actual main's next request and pinned HAL disable path is complete. Physical power, full boot, and display remain unverified.

Actual scan-profile main requests DEVPWREN `40021004`=0 with CFG `2171010` (ADCEN 0/RPTEN 0), timer stopped, and FIFO empty. It reuses ADC entry mask `2000` and STATUS `40021008` from the existing stock24 table. HAL disable clears only the relevant enable mask, checks until status clears, and returns timeout/error. See private `adc-power-off-research-01/source-report.json` and existing `adc-shared-power-research-01` table evidence.

Explicitly select `--adc-power-off-response off|stuck-on`. It requires the constant scan profile. The transition on → off-requested is allowed only with ADCEN 0, timer stopped, and FIFO empty. This conservative model policy does not prove the actual bus fault policy or all hardware-required ordering. Request mask becomes 0 immediately; the next status read returns 0 or `2000`. Zero response delay is a virtual assumption. The epoch is retired immediately on request and re-enable is blocked. GPU sibling bit and epoch are preserved. Without selection, the existing power-off request block remains.

Continued firmware progress in stuck-on is not evidence of safe error handling or actual power-off. This is a digital response for one epoch and does not model reset/restart, analog rail, or real-device recovery.

## Verification results

Private `adc-power-off-verification-01/final-verification.json` confirms 56 unit assertions (existing scan 39 + off 17), six shared-bank native regressions, actual main 5, and source snapshot agreement. Rejection for quiescence=false checks a collective domain boolean, not measured individual hardware conditions. Successful mains have actual CFG 0, timer stopped, and FIFO empty.

With explicit off response, stock 2.4, stock 2.3, and Faceclaw recorded ADC request/status 0, powered-off, off_requests 1, and retired epoch, then stopped at DEVPWREN `40021004`=`400`. This is the pinned header's PWRENUART1 mask. PC is `494d78` for stock 2.4 and `488e90` for the others. GPU remains powered-off/retired.

Stock 2.4 stuck-on progressed to the same UART1 request while ADC status remained `2000`. This observation does not establish safe stop, error handling, or recovery on failure. The default unselected case is blocked at the existing ADC off 0 request at `494f3e`. Three sample consumptions and stopped timer/ADC state are preserved in all cases; actual power, full boot, and integrated display remain unverified. The new CLI off option's dependencies were confirmed rejected before input and Docker. Next is UART1 power/initialization source research.

Follow-up bw542: the single-epoch re-enable rejection above describes the scope supported at the time. The next cycle after completed powered-off/status 0/quiescent was extended and verified in [original boot/main power cycle](../../bootloader/original-boot-adc-power-cycle.md). Failed or incomplete off states remain rejected.
