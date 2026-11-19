# Astra Review of Emulator Development Direction

bw-0125. At the user's request, an independent `gpt-6-astra` agent using high reasoning conducted a read-only review. It examined repository instructions, design, runner, checkers, existing artifacts, and official Renode documentation. It did not modify files, rerun firmware, access devices, or publish externally during the review. The parent saved this summary and the work record. No separate transcript archive was provided.

## Assessment

Running the original main firmware on Renode M55 and modeling the necessary peripherals is an appropriate direction. The immediate bottleneck is the repetitive structure that requires changes to execution configuration, generated scripts, and existing endpoint checks for each added register, rather than the CPU engine. There is no basis for switching to a function bridge or implementing the whole chipset in advance.

Evidence includes the many CLI options and string substitutions in `tools/run_renode_main_probe.py`, the large shared constructor in `tools/renode-strict-mmio.cs`, and per-endpoint counter checks in `tools/verify_iom_evidence.py`. Actual generated-script syntax errors and a failed historical UART counter assumption are recorded in `docs/hardware/power/iom-startup-instance-set.md`.

## Sequence for next work

1. Bundle the three bw122 original executions into one pinned profile and common reproduction/check command. Use existing frozen inputs and models without mixing in the bw124 RTC change. Exclude broad refactoring that changes model behavior. Collect original, container, model, and profile hashes and all assumptions in a manifest, and syntax-check the generated script before native execution. Run stock 2.3, Faceclaw 38, and stock 2.4 sequentially and check existing strict endpoints, inputs, and source. Measure preparation, native execution, and audit times separately. Separate the common contract for unchanged originals and blocking unsupported operations from per-endpoint counter expectations.
2. Add limited read-only execution observation. Keep bounded records of confirmed patch-address entry counts, major initialization boundaries, and recent MMIO events. Check Renode 1.17 tracing/profiler first. Distinguish unconfirmed function names by address and confidence. Separate the guest execution budget from the host emergency timeout so instrumentation load does not change the observed endpoint.
3. Extend peripherals by meaningful units of behavior. Set observation goals such as initialization-function return, first UART transfer/ISR, application event, or display submission, and investigate the relevant HAL and call paths. Keep strict stops on unknown accesses; do not add success constants merely to pass.

Development speedup multiples and the time required for the first task are not measured results. First measure the actual repeat cost with a small execution profile without expanding scope. The RTC latch passed only 38 standalone conditions; original main verification after the change had not yet been performed. Preserve bw124 in that state.

## Alternatives and boundaries to retain

- Expand to the full chipset, other processors, and physical timing when the actual target path requires them.
- A host function bridge may support auxiliary UI/protocol experiments, but is not recommended for the primary execution used to verify the original path.
- The independent renderer and web transport model are auxiliary tools and must be distinguished from evidence of integrated main display and recovery.
- Consider snapshot acceleration after measuring preparation/boot cost as a bottleneck. Reuse after model or version changes is risky.
- For the GPU, identify the actual submission/display transfer boundary first, then implement the required command and memory effects.

The current main reset execution is not a full boot including ROM, bootloader, and other processors. Synthetic INFO1, power, ADC, and CQ assumptions determine branches. The latest original main TX/ISR/I2C/CQ counts are 0; the application loop and integrated display are incomplete. Preserve the original hash, prohibition on forced PC/return-value changes, strict unsupported-access stops, explicit assumptions, and per-operation approval for physical device work. Product completion criteria stand at 13/29 and do not increase due to this review.

Official Renode references: [execution tracing](https://renode.readthedocs.io/en/latest/execution-tracing/execution-tracing.html), [saving state](https://renode.readthedocs.io/en/latest/basic/saving.html). The official latest documentation is not evidence that a feature was verified in the pinned 1.17 runtime.
