# Original controller reset boundary after timeout

bw407. **The natural timeout path of stock 2.4 main emitted an actual GPIO reset, but stopped at the existing virtual controller's single-use policy.** Original, model, board, clock, and timeout settings were unchanged. Overall 7/16 (43.8%) and E14 partial remain.

## Actual execution

The bw405 response-loss input was reused unchanged, observing reset 93 and CS 149 writes in GPIO output events after clean close. No additional CPU hooks, branch changes, ACK/credit injection, or host reset calls were used. Existing HCI observer and protective stop boundary remained.

The fifth of six calls in the original timeout callback, `563d1c → 4dcec0`, calls initialization at `5013f8`. After pin setup at `5012a4`, this enters `501ba0`. That function passes reset 93 low at `501bcc–501bd0` and high at `501bda–501bde` to GPIO function `4966be`. Original bytes were audited.

| LR of reset write | Value | Observed peer state |
| --- | ---: | --- |
| 5013eb | low | Exhausted |
| 5012f3 | low | Exhausted |
| 501bd5 | low | Exhausted |
| 501be3 | high | Exhausted |

Repeated lows after the first did not update the assertion epoch. First assertion was 19,108,717 µs and release 19,126,501 µs, a **17,784 µs** pulse. It met the current model's 1 µs minimum, so the reset adapter became held=false/released=true. CS was known/high for all four reset writes. This is a result of the current virtual clock and explicit timing fixture, not physical reset timing verification.

Peer Frames/Commands/Replies remained 246/59/60. The original then read RDY address `40010410` at `50190c` and stopped with one guard and zero CPU faults. The timeout callback did not return.

## Cause and next contract

Existing `HoldReset()` transitions to `Exhausted` if Frames>0 already in the read scenario. `QualifiedRelease(valid)` does not change that state. Thus this is an **explicit unsupported model boundary** that supplies no subsequent transport handshake even with a valid-length original pulse, not evidence that firmware sent an invalid pulse.

The next model change is limited to opt-in reset generation. It must check original reset assertion/release and pulse conditions, CS and incomplete transport state, and previous generation termination, then revalidate the initial handshake and pinned startup commands in a new generation. Separate previous cumulative audit material and per-generation counters; continue rejecting invalid commands, short pulses, and reuse without reset. Simply clearing `Exhausted` or returning success for every command does not satisfy this contract. Reinitialization, final error-notification consumption, and successful reconnection remain unverified.

## Observation control and audit

The additional GPIO observation run matched bw405 fault, existing four JSON report values, and complete ATT/close/final SRAM. Main, strict model, board, initial SRAM/ITCM, and profile were byte-identical. Collected R0–R15, time, and guard appear in existing reports. This compares collected state for one input; it does not guarantee all special registers, peripherals, or existing observers are unaffected. Raw JSON byte identity is reported separately from value identity.

Sixteen audit checks, pinned tool report byte identity, and 14 progress-management checks passed. Three cases jointly tampering with pulse minimum, CS, and reset writes across JSON/log/hash were rejected. The first negative's fixed index selected a row already containing CS, so an unchanged control passed. That run was retained but not counted as tamper verification; three separate cases selecting the actual first reset row were checked.

Tools: `probe_controller_reset_boundary.py`, `renode-controller-reset-observer.cs`, `verify_controller_reset_boundary.py`. Private: `controller-reset-boundary-native-01`, `controller-reset-boundary-research-01`. No physical access, Astra/subagent, or external posting.
