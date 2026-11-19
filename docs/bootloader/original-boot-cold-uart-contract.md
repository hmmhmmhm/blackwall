# UART cold power request during original boot

Status: bw528 in progress. This does not verify physical power, UART wiring, or physical timing.

Bw527's shared request had before=0, proposed=0x400, XOR=0x400. Comparison with actual UART1 mask=0x400 and zero requests from other owners identified it as a UART1 request. ADC had already been powered down by original code; buck request/transition was 0.

Pinned HAL generic peripheral enable was compared with the original cold call. Since the SDK may call SPOT policy, absence of a direct buck check in code is not generalized to absence of electrical prerequisites for every peripheral. This change removes buck-active conditions only at two UART dispatch points and uses explicit UART response profiles. IOM/MSPI/OTP/crypto gates and GPU initialization conditions remain.

UART quiescent shutdown conditions, partial/concurrent write blocking, shared HCPA status, register reset after last-user shutdown, and reactivation policy remain. CPU PC/branches/returns and buck phase are not forced.

## Verification

- `private:simulator/boot-uart-source-bw528-01/change-proof.json`: exactly two UART dispatches changed.
- `private:simulator/boot-uart-cold-red-bw528-01/report.json`: previous model blocked first UART power request.
- `private:simulator/boot-uart-cold-green-bw528-02/report.json`: 35 checks passed, covering four UART cold requests/responses, busy-off rejection, quiescent off/reactivation, and shared gate.
- `private:simulator/boot-uart-hcpa-regression-bw528-01/report.json`: existing 38 HCPA checks passed.

The first GREEN candidate's status test incorrectly assumed the entire status word must equal one UART mask while shared HCPA was on. Existing model supplies shared-domain status 0x1e00, so the test was corrected to check the requested UART bit and logical UART status separately. No additional model change was made.

Two previous ADC cold conditions rejecting UART cold were replaced by the new UART contract. Existing 44-check ADC evidence remains as a record of the model at that time, distinct from current regression.

## Original execution and cleanup

Additional ADC regression passed all 40 checks across two profiles. The original made one UART1 power request/response each and set CR=8, then stopped after 13,791,561 instructions at PC 0x4234a2 on write 0 to MCUCTRL.D2ASPARE (0x400201b0). Code/system protection and CFSR/HFSR errors were 0; main/frame were not reached. Authoritative record: `private:simulator/original-boot-uart-cold-native-bw528-01/frontier-proof.json`.

An identical 149773-byte boot dump was checked and removed; owned containers for all six runs were confirmed removed. Execution source, model, logs, SHAs, and reproduction commands remain.
