# Credit restoration and virtual reconnection after original timeout

bw411. **In the pinned stock 2.4 virtual scenario, completion loss → original timeout → controller reset/reinitialization → credit restoration → original DM handler return for a new connection were confirmed.** This verifies one scenario, not normal GAF, recovery of other originals, or all ATT/app functionality on a new connection. E14 partial and overall 7/16 (43.8%) remain.

## Pinned input and resumption

The actually verified bw410 `post-reset-advertising-native-02` input was copied after checking manifest/hash. Main, model, board, clock, and profile were not regenerated or changed. The additional observer registers hooks only after the existing healthy stop. Previous nine JSON report values and four complete SRAM snapshots matched bw410. This comparison scope is distinct from raw JSON byte identity.

Execution began at original PC 563d32. The next original instructions are `movs r0,#1` and `strb.w r0,[r4,#22]`. After execution without host register/PC/credit/state writes, observation stopped before original ready-function return instruction 563d3e. Actual credit changed 0→1 in the original WSF task and Thread context. Timer was inactive, opcode 200a, and new startup 59 commands/60 responses retained.

That return instruction was also naturally resumed, followed by about 100 ms of virtual cleanup. All three CCB slots were state=0/active=0, peer Complete/events 0/pending=false, and credit 1. An old handle byte remaining in the first slot is not interpreted as failure or full memory zeroing. The original release decision is based on state/active.

## New virtual connection and original handling

Only after checking those conditions, the existing peer's `TryQueueRuntimeConnection()` supplied a fixed LE connection-complete event. This was not actual BLE or a connection to another device. CPU PC and time immediately before input were preserved, and GPIO 117 pending/IRQ occurred.

Through original ISR and SPI/HCI/DM paths, opened function 4d3f1a was called once, stopping at return instruction 4d3fc4. No synthetic caller or register seed was added. A new observer separately recorded this call without bypassing the existing observer's stopped state.

Checked state:

- One CCB was reassigned state 3/active 1, handle 40, peripheral role.
- Status, handle, and virtual peer address in the actual 36-byte decoded event matched fixed input.
- The same original WSF task, Thread context, 16-byte function stack range, and kernel stack bounds were satisfied.
- One new ISR entry, GPIO edge 8→9, and original callback counter 0→1 were confirmed.
- New-generation runtime event 0→1, pending/IRQ clear, startup 59/60, credit 1, and inactive timer remained.
- Guard/CPU fault/memory-policy violations were 0 throughout.
- One RTC commit remained and matched virtual elapsed time within 10 ms resolution without additional writes.

Sensors are in the explicit frozen-core fault/pending and calculation 0 state. Do not expand this success into normal sensor service, full boot, radio timing, or a guarantee of physical recovery.

## Scope and next work

This run confirmed the original DM return boundary of the new connection. Subsequent ATT/TPL, display/UI, and app reuse remain unverified. The same long-delay, response-loss, reinitialization/reconnection native path remains for stock 2.3/Faceclaw. Extend it against each original's exact ABI/profile, distinguishing existing immediate-disconnect/invalid-message material.

Twenty-four audit checks covered pinned input, prior-state identity, actual credit store, cleanup/reassignment, decoded event, original task/stack, IRQ, RTC, and guard. The pinned tool report is byte-identical. Three cases consistently tampering with unrestored credit, stale CCB before input, and unconsumed IRQ across JSON/log/hash and necessary SRAM were rejected. Fourteen progress-management checks also passed. The 16 acceptance criteria and states were unchanged.

Tools: `probe_post_timeout_reconnect.py`, `renode-hci-credit-observer.cs`, `verify_post_timeout_reconnect.py`. Private: `post-timeout-reconnect-native-01`, `post-timeout-reconnect-research-01`. No physical device, Astra/subagent, or external posting.
