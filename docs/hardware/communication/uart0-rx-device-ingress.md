# UART0 device RX input and original receive task

bw364. Existing M55 board and original main are used without hardware access. The test caller creating requests through the original API remains, while response input is placed in an optional UART0 FIFO instead of directly calling receive. This is not completion of natural main or complete peer communication.

## Supported contract

`BlackwallUartAdapter` receiveFifo defaults false and is selectable only for UART0 with interrupts enabled. It accepts clean-byte bursts only and checks UART power, enable, RX enable, clock selection, 8-bit configuration, and remaining FIFO capacity. Injection is rejected in full if it exceeds the 32-byte FIFO or one-byte capacity with FIFO off. DR reads pop from the actual PL011 queue and record byte count and FNV1a64 order hash. FIFO threshold follows guest IFLS settings. IRQ updates after mask/clear/DR drain. FIFO mode changes while receive is pending are rejected, and reset/powerdown clears receive state.

The reuse basis is pinned Renode PL011/UARTBase, not hardware identity certification. Current runtime unit tests cover threshold, order, state, capacity, IRQ, power/reset, profile rejection, and native half-FIFO configuration: no IRQ at 12/15 bytes, IRQ at 16 bytes, through drain, totaling 32 judgments. Initial unit tests failed by assuming IFLS reset 0. Backend reset 0x12 (RX select 2) was confirmed and the test corrected to explicitly set IFLS 0. The model's default threshold was not changed.

## Original configuration and input

Config 20002b9c in stock24 saved SRAM contains baud 921600 and RX level 2. It was linked to the literal at original 57f270 and HAL 5adf90–5adfa2 writing config+0xb→IFLS[5:3]. Callback slot 200770e0 registers 4fdce1. Native observation also confirmed control 319, RX select 2, and mask 1fd0. This is a 16-byte threshold, half the 32-byte FIFO.

No arbitrary padding is added to one normal 12-byte response and no IRQ is forced. The 24-byte device test consists of two complete 12-byte protocol frames corresponding to the original request ID. `uart-rx-crc-pair` has two frames with incorrect header CRC; `uart-rx-crc-then-valid` has an erroneous frame followed by a valid one. This is a continuous input scenario exceeding the original configured threshold, not evidence that a standalone or split 12-byte frame is supported.

**RX timeout, error frames, overrun, and physical transmission time are currently unsupported.** Do not automatically set a timeout flag without an exact timeout assertion/clear contract. Do not expand unit-test scope to all UART behavior.

## Execution path and results

Original Sensor Thread/stack is preserved through the transmit-completion checkpoint. Then original queue creation and blocking get API make the test caller wait, allowing the original scheduler to run the receive task. The host does not align TCB, SP, BASEPRI, or PC to the receive function or directly call callback/receive. The receive-entry observer records pointer/length/SP/LR/TCB/xPSR and stops just before original receive pop. Thus green means **reaching the function return point**, distinct from complete task return after pop. Observer neutrality is not established.

Error-pair native runs in three originals (stock24/stock23/Faceclaw) each passed 23 judgments. Saved audits added parser reset and pending-request preservation, each passing 25: actual 24-byte FIFO pop/hash, UART0 IRQ vector 31, SRAM buffer delivery of 24 bytes from original uart_sync_thread, two CRC errors/UI queue 0, matching 16-byte prologue stack at original receive return point, and zero CPU faults/unsupported accesses. This is evidence connecting exact RX input with parser error consumption. Three synthetic negatives independently tampering byte-order hash, receive TCB, and RX IRQ while consistently updating raw JSON/log/hash were all rejected by semantic checks. This is not normal reply/UI or complete E13.

The first stream including a normal reply retained six failures out of 23 judgments. The 24-byte drain, IRQ, receive task/entry, and first CRC error were confirmed, but displaydrv_mgr_task attempted an MSPI0 40060000 write (guard name: guard_iom7_tail) at PC 4e8a46 and strictly stopped. Final return of normal receive function and UI queue effect remain unverified. This is not overwritten as success, nor is normal peer functionality substituted with the error pair. The next dependency is connecting this original display initialization path to the existing MSPI0 contract.

## Model change and default-path control

The whole existing frozen strict.cs is not replaced with the current model. Only one UART adapter class block is substituted using saved before/after source and SHA; other model bytes remain. RX option is enabled only in UART0 board entry. Main and initial SRAM/ITCM are unchanged. Input/capture hashes, raw JSON/log agreement, and schema 2 semantic judgments remain. Saved audits do not rerun the current candidate builder.

Stock24 native transmission using the new UART component with RX off passed the existing 15 judgments. All observed fields projected from existing transmission and complete SRAM were exact. The initial full JSON comparison failed due to CRC/RX observation fields and extended mailbox absent from the historical send capture; that failure was retained. Subsequent comparison retained all existing fields and original mailbox range, separately indicating the two new mailbox words were 0. This is not expanded to universal observer neutrality or default-path preservation for all profiles.

Existing default adapter 117 judgments and enable IRQ 64 judgments were reused; the current checker passed saved audits of six historical native send/CRC cases, 108 judgments. These were not reverified through new native execution. Fourteen progress-management tests also passed.

## Reproduction and saved audit

The public runner is existing `tools/run_sync_transport_m55.py`. Simulator and result paths must be outside Git, with new folders per execution/audit.

```sh
<private-python> tools/run_sync_transport_m55.py <simulator> <new-output> \
  --case stock24 --scenario uart-rx-crc-pair
<private-python> tools/run_sync_transport_m55.py <simulator> <existing-output> \
  --case stock24 --scenario uart-rx-crc-pair \
  --audit-existing --audit-output <new-audit>
```

Private material: simulator/uart0-rx-native-control-01, uart0-rx-native-stream-01, uart0-rx-native-crc-pair-01, uart0-rx-research-01. Source, verification, limitations, frozen runner, and hashes are preserved in the research manifest. Proprietary images and SRAM dumps are not committed to Git.

Bw364 complete normal RX/UI, short-frame timeout, and actual root request production remain incomplete. Overall 4/16=25.0% and API checklist 3/6 remain.

## bw366 address-owner correction

40060000 is MSPI0; IOM7 is 40057000. guard_iom7_tail is only the name of a broad unsupported address region, not the cause device's name. This corrects the IOM7 description in the bw364-era record. Follow-up connecting existing MSPI0/JBD state profiles follows [MSPI0 integration](uart-rx-display-mspi0-integration.md).
