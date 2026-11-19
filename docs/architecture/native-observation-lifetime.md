# Native Observation Interval and Execution Lifetime

bw-0286. The execution contract was improved following expiration of the 45-second observation in the bw285 stock 2.4 run. The historical run was not restarted; tool tests and a new stock 2.3 control verified the change.

## Change

Schema 2 plan `execution_mode: "until-guest-stop"` waits for the original guest's strict stop. It removes only the known inherited host observation deadline; `IsPaused` checks, one-second polling, five-second heartbeat, original post-stop checks, and memory-export conditions remain. No observer manipulating guest instructions, PC, IRQ, or RAM was added.

This mode cannot be used with `host_capture_seconds` or with a bounded-capture semantic contract. Missing, duplicate, or unknown loop forms are rejected before execution. An existing guest-stop loop is not changed again. Existing plans were unchanged.

Native children in this mode have no host timeout, and output is written directly to `renode.log` from startup. The `execute` stream argument defaults to false, preserving existing caller behavior. Heartbeats can be checked during execution, and the same tool session is polled to terminal state. Do not restart because logs are temporarily absent or observation time has elapsed. Clean up only the unique task container after that run has actually terminated.

This policy waits until guest stop. It does not treat a guest that never stops as a boot success or guarantee an automatic solution for infinite execution. While running, check the actual process handle together with logs. Do not judge liveness or termination from a state file alone.

## Verification

Twenty-five host conditions and the same 25 rerun on a pinned copy passed. Eight new conditions include:

- Observation-loop mode selection, unchanged default, duplicate/unknown rejection, and reuse of an already changed loop.
- A mock-clock control where the previous 45-loop run ends before guest stop, but the new mode continues until guest stop at 47 loops. This is not evidence of a real 47-second Renode execution.
- Reading a real Python child's READY log while running, confirming its PID is alive, and then observing the same child terminate with FINISHED. No separate run was created midway.
- Preserving stdout/stderr logs even on abnormal exit.

Initial RED was absence of the new helper/stream argument. An added valid+unknown duplicate-loop test also failed once; it was fixed to count all relevant loops together.

The stock 2.3 off control in `native-guest-stop-candidate.json` was run on actual Renode M55. A 15-second heartbeat and live session were confirmed while running; after termination, existing CPU, instruction count, events, and strict boundary were exact. Saved SRAM export and a separate audit also passed. Do not claim actual native execution exceeded 45 seconds. Deadline removal was checked through loop tests and generated runtime; native fidelity was checked by this control.

Simulator material outside Git is retained at `native-guest-stop-control-01/stock23`, `native-guest-stop-audit-01/stock23`, and `native-observation-verification-01/manifest.json`. Twenty-nine Python files and three test files were pinned; two runners were changed dependencies. Four peripheral models and the web gate match previous SHA values. The earlier incomplete stock 2.4 capture was also retained.

## Next

Because the tool change and actual control were verified, perform the remaining bw285 stock 2.4 integration verification with a separate plan using the new contract. Do not turn the historical 45-second run into a success or simply retry it. Overall product condition fulfillment remains 44.8%, and physical-device approval boundaries remain unchanged.
