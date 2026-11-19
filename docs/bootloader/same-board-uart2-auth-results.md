# Same-board UART2 authentication decisions and remaining idle boundary

2026-11-17 · bw-0577. Overall **10/12=83.3%**. BV05/06 remain incomplete; physical installation/recovery was not verified. Actual UART2 FIFO reception was connected under pinned current 2.3 patch/same-bundle main and synthetic B0/trim 1.

## Behavior verified

| Final scenario | Actual original result |
| --- | --- |
| No input | Natural main entry after worker/HELO |
| Invalid HMAC, 25 bytes | 25 bytes consumed, live session held/claimed both remain 0, natural main entry after receive re-entry |
| Valid HMAC, 25 bytes | Original code records held=1/claimed=1; strict stop in CPD preparation before OKAY |
| Valid retry after invalid HMAC | 50 bytes consumed/two receive entries, unclaimed before retry, held=1/claimed=1 after valid retry |
| Timeout after partial 8 bytes, then valid retry | After 157 ticks, valid 25 bytes added; 33 total consumed/two receives, unclaimed before retry and held=1/claimed=1 after |

Actual receive FNV64 for each final input was independently compared with Python HMAC/frame generation. Negative request flips one HMAC bit and correctly recalculates checksum. The original public default-key artifact's key ID was checked. No device secret or personal key was used.

The valid request executed original HMAC comparison and session writes, not merely a virtual-peer success return. However, wire OKAY had not yet been received, so this is not complete authentication transaction completion. `virtual_peer.accepted=false` and `scope.authentication_verified=false` retain that limitation. CONT/recovery commands had not yet been transmitted.

## Model and observation boundaries

- Existing PL011 adapter `receiveFifo` option was allowed for UART2 too. Default off, UART1/3 rejection, and UART0 RX timeout option remain. FIFO32 power, format, capacity, order, and atomic overflow rejection are reused.
- Virtual peer supplies only external UART bytes via `TryReceive` while the machine is stopped. It does not write PC, guest RAM, RTOS, or branches, or enable UART2 IRQ from host.
- Additional `peer-receive` PC observation changes execution setup. All five final cases use the same observer/model, but full execution identity to a hook-free baseline is not claimed. Host pause is wall-time-based, so exact tick/time comparison is not claimed.
- Pinned literal of original Thread/Handler tick accessor is `0x20027148`; read-only access calculated the partial-frame retry interval.
- IRQ exception counter had no separate IRQ probe attached, so it was not used as evidence that no IRQ occurred.

## Next boundary

All three normal/retry cases stopped at `PC 0x41ca00` attempting to write `0x22` to `PWRMODCTL.CPDLPSTATE 0xe001e300`. CPU fault, memory policy, and system-control violations were 0; this was the sole strict boundary. It corresponds to deep-sleep ELP/CLP retention preparation in public HAL `am_hal_sysctrl_sleep`. It evidences an original configuration request, not actual deep sleep or successful wake.

Existing normal-sleep model has an `0x11` contract; do not unconditionally allow `0x22`. Next investigate original boot deep-sleep preparation→flush/WFI→wake return contract and existing model reuse, verifying what can be stated as an opt-in functional model. Actual retention, power, and silicon accuracy remain separate.

## Verification, failures, and cleanup

UART2 FIFO unit 23, UART0 RX timeout regression 49, and runner unit 5 passed. A 79-check audit of final five native source/bytes/sessions/boundaries was frozen, and `/tmp` rerun also passed 79. Original boot/main hashes remained unchanged in all result-collection runs.

First harness stopped before firmware execution due to HMAC assembly import failure. Independent HMAC vector preflight verified .NET assembly reference. Later synchronous RunFor did not return on stop, so only the two corresponding owned containers were terminated. One exited 139 and is not included as a valid authentication result. Collection was changed to existing asynchronous StartAll/pause/FIFO/resume. Initial native04 confirmed input consumption/stop, 05 added session diagnosis, and final same-observer control is 06. First audit's UART0 journal name error (renode instead of native) was corrected without weakening results.

Fourteen owned native jobs confirmed removed and current container absence checked. Thirty-four duplicate firmware files totaling **69,399,916 bytes** were cleaned up. Source/model/log/hash and key failure diagnostics remain; ephemeral build/cache was removed with containers.

Final evidence: `private:simulator/uart2-auth-audit-bw577-04/{report,cleanup-summary}.json`; individual native locations/hashes follow report cases. Distinguish prior [worker/main integration](b0-power-recovery-results.md) boot success from this authentication/idle boundary.
