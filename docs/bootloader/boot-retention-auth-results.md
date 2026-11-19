# Boot retention/WFI and authentication response integration

2026-11-17 · bw-0578. Overall verification is **10/12=83.3%**; BV05/06 remain incomplete. With synthetic B0/trim 1, this task confirmed **original HMAC decision → OKAY → CONT reception → RLSD transmission and session release**. The next watchdog feed exposed a missing DWT device; main was not yet entered.

## Reused behavior contract

Existing frozen `BlackwallCpuNormalSleep` already had context-qualified retention staging/flush. Rather than duplicate it, `cpu_retention_staging_model.compose_boot_binding` extended constructor address validation only.

- With `bootRetentionBinding=true`, only original 2.3 store `0x41ca00`, return `0x41a7c0`, and flush `0x41a9ce` are accepted; any mismatch is rejected. Existing main address range/default policy remains.
- Existing checks of actual CPU PC/LR and current SP arguments `[0,2,2]` remain. CPDLPSTATE `0x22` writes are not permitted from arbitrary locations.
- Existing flush also checks guest PC/base register, CPD value, staging count, and SCR.SLEEPDEEP state. This read is an explicit synchronous bus fixture, not a physical APB-latency model.
- TryRead/TryWrite/flush and retention handling bodies are byte-identical to frozen original. Only constructor and explicit board address binding changed. Actual WFI/interrupt waiting is left to Renode; host did not change firmware, IRQ, PC, or stack.

Public HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` sysctrl/pwrctrl code and ELP/CLP retention enums were compared. Original boot flush literal `0x47ff0000`, actual load/WFI, and CPD store instructions were confirmed in the pinned image. Physical retention, power, and cycle accuracy are not certified.

## Actual observations

| Observation | Result |
| --- | --- |
| Context-qualified CPD staging/flush | 3 each |
| Original WFI `0x41a9d4` / return `0x41a9d6` | 3 each, alternating order |
| Final CPD state | Restored to 0 by original |
| Actual UART2 receive | HOLD 25 + CONT 9 = 34 bytes, independent FNV64 matches |
| Actual UART2 transmit | HELO 21 + OKAY 29 + RLSD 13 = 63 bytes |
| Authentication response | Entire frame matches independent Python HMAC/checksum |
| Session | `[held=1,target=0,claimed=1,receiving=0]` at OKAY observation; `[0,0,1,0]` at end |
| Original images/faults/observations | Full boot/main hashes unchanged; CPU fault/policy/missed observations 0 |

Peer state remained `continue` because the engine stopped before the next host observation. Complete original RLSD transmission and original held release were confirmed by separate final checks. This string is not used to judge recovery complete.

## New unsupported boundary and stronger classification

After session termination, original `boot_watchdog_feed` uses `DWT.CTRL 0xe0001000` and `DWT.CYCCNT 0xe0001004`. The current board lacks this device; Renode recorded a non-existent peripheral warning and the machine ended aborted at watchdog-feed `PC 0x434aec`. Warning return 0 is not treated as an actual DWT value or verified polling fallback. Feed success, normal power-down, and main handoff remain incomplete.

The first saved result's general classification was `stopped-unclassified`, with conservative false scope authentication fields. Without overwriting this evidence, final audit explicitly records wire authentication/release=true and corrected classification=`unsupported-engine`. Subsequent runner classification treats non-existent-device warnings as unsupported-engine and aborted without guard as engine-aborted. Authentication is elevated only with original OKAY confirmation and live held/claimed, not worker/HELO alone.

Pinned Renode source includes `Miscellaneous.DWT` using a virtual-clock LimitTimer. Next verify actual pinned runtime type, enable/counter/wrap contract, and clock assumption before explicitly connecting it to the board. A time-based counter is not equated with actual M55 cycle accuracy. Then continue original watchdog bus behavior, return to main, and error/timeout controls.

## Verification and cleanup

Twenty constructor/existing-main-policy/non-context host `0x22` rejection checks passed GREEN after RED (missing new argument). One actual native, 25 frozen-audit checks, 25 `/tmp` rerun checks, five existing-runner and three classification tests passed. The audit's initial sysctrl source-path error (hal/mcu) was corrected to the actual pinned tree path.

Three owned jobs terminated and current container absence confirmed. Four duplicate firmware files totaling **8,164,696 bytes** were cleaned up; originals, hashes, source, model, logs, RED diagnostics, and audits retained. Ephemeral build/cache was removed with containers.

Evidence: `private:simulator/boot-retention-auth-native-bw578-01/`, `private:simulator/boot-retention-auth-audit-bw578-02/{report,cleanup-summary}.json`. Distinguish the partial authentication in [previous UART2 assessment](same-board-uart2-auth-results.md) from completed wire response here.
