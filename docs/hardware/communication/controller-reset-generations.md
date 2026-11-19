# Limited controller reset generations

bw408. **Opt-in reset generations were added to the virtual controller. The original timeout callback passed the previous RDY guard boundary and reached its return instruction.** Complete recovery, asynchronous initialization completion, and consumption of app error notification remain separately unverified. Overall 7/16 (43.8%) and E14 partial are retained.

## Model contract

Existing shared `renode-em9305-reset.cs` is unchanged. An extension specified by `controller_reset_generation_model.py` is composed into the pinned reconnect/loss component. `controllerResetLimit` defaults to 0 for the existing single-use policy; 1–4 specify the number of subsequent generations allowed. The experiment is limited to 1. Enabling without the readvertising profile or using an out-of-range value is rejected.

A subsequent generation starts only on original GPIO reset assertion/release. Assertion checks CS known/high, completion of all previous startup commands/responses, no pending event, no incomplete runtime write, and remaining generations. Release requires a pulse accepted by the existing reset adapter and CS high. Repeated low preserves the first assertion's eligibility and time. Short pulse, CS low, incomplete startup/response/write, release without reset, and exceeded limit fail closed. Frame 0 of a new generation is not exempt from the limit.

The previous generation's frame/command/response/runtime event/readvertising and loss counters and actual accepted startup/readvertising commands remain in history. The new generation resets counters, transfer buffer, and runtime pending state and revalidates the same pinned handshake and startup commands/responses from the beginning. The host does not call counter reset or change firmware PC, branch, timer, or credit. Response fixtures are not a complete physical controller implementation.

## Actual original execution

The existing input is stock 2.4 main reset → virtual ATT/time → disconnect delayed 1000 ms → loss of one readvertising completion → original WSF timeout → original reset pulse. Sensors use the explicit frozen-core failure profile, not normal GAF execution.

Original reset 93 low 3/high 1, 17,784 µs pulse, and CS high were confirmed unchanged. The first generation's 246 frames, 59 commands, 60 replies, 4 runtime events, and readvertising command 1/reply 0/drop 1 were preserved, and a new handshake began in generation 1. The next two original initial commands and two responses were handled.

The previous `Exhausted`/RDY guard did not occur. Execution reached the original timeout's sixth call `563d20 → 4dab5e`, and the existing observer stopped before the callback return instruction at `563d24`. The original WSF task, Thread context, pushed 8-byte stack, and original return address were confirmed. **Reaching the return instruction is distinct from actually executing it.** Current material does not prove the latter.

The two initial handshake/version responses are not completion of all 59 startup operations. The original subsequent function contains code to send event `38` notification to handler 1 of descriptor `200762d4`, but actual allocation, transmission, and consumption were not separately observed. Final credit remains 0; the host did not restore original HCI timer/opcode. Next is verification of actual notification handling after return, asynchronous initialization, and communication resumption.

## Controls and verification

Three candidate enabled runs had identical collected report values and complete SRAM. This is a comparison under pinned input, not a claim of equivalence across all paths. Final enabled audit 20 checks and disabled audit 14 checks passed, and each pinned tool report was byte-identical. The disabled run also matched the existing failure's final full SRAM and HCI/GPIO report values. Final candidate enabled/disabled runs and three initial development runs are distinguished in the private manifest.

Three cases consistently tampering with generation history deletion, a different task, and CS low at release across JSON/log/hash were rejected. Fourteen progress-management checks also passed. The 16 acceptance criteria and their states were unchanged.

The Renode unit test's 104 assertions checked valid generations, new startup, invalid bytes, short pulse, CS selection, pending event, incomplete startup/runtime write, release without reset, generation limit at frame 0, and machine-reset initialization. The default-off control's 55 checks also passed. Unit-test startup is primed with an existing fixed fixture and is not represented as an independent command-content oracle or original main execution.

During development an incorrectly entered first command opcode was corrected to actual fixed value `0101fd05884bf00008`. A condition that mistook existing behavior leaving a completed last command in the buffer for an incomplete command was then fixed. Completed buffers are allowed, while incomplete runtime write types are rejected. Failed tools and runs are retained privately. Frame 0 of the first and subsequent generations were also distinguished to prevent bypassing the limit.

Tools: `controller_reset_generation_model.py`, `verify_controller_reset_generations.py`, `probe_controller_reset_generations.py`, `verify_controller_generation_capture.py`. Private: `controller-reset-generations-research-01`, `controller-reset-generations-native-*`. No physical device, Astra/subagent, or external posting.
