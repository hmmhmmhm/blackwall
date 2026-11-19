# One-Time Astra Review of Direction and Workflow

User-requested one-time review, task `bw-0230`. One `gpt-6-astra` agent received the overall objective, current documents, models, and original execution evidence. No additional agents or subsequent Astra calls were made. The review used reading and host analysis only; it involved no device access, file modification, or native execution.

## Conclusion

Continue executing the original ARM binary from reset without hiding unsupported accesses. Recent HCPA results represent progress through the original UART shutdown, restart, and configuration restoration. There is no basis for discarding existing evidence or restarting the whole chip model.

However, continually chaining small probes and audit tools has begun to harm reproducibility and maintainability. At review time there were 217 started tasks, 330 Python tools, 20 C# models, and 220 Markdown documents. These are observations of scale at that time, not product progress metrics. Frontier progress in a diagnostic path without the normal font bank must not be converted into progress toward normal display.

## Findings and changes

| Review finding | Verification and response |
| --- | --- |
| High: global replacement of models for cache changes broke past audits | The parent reproduced exit 1, `Model differs beyond pinned reviewed delta`, in the existing HCPA `--audit-existing`. Reverted the global `verify_timer14.py` change and separated new candidate assembly into `dcache_address_models.py`. Modified historic audit-existing to verify saved model core/tail and pinned SHA instead of the current core/builder. |
| Medium: the 51 cache unit checks use direct TryWrite calls and do not prove actual bus connection | Completed integration verification using three original main inputs and option-off controls. All three originals passed one real CPU cache clean and reached the DMA destination configuration boundary. The unit model was byte-identical, so the same 51 native checks were not repeated. |
| Medium: risk of presenting progress in fontless diagnostics as normal display | Elevated the normal font bank, embedded bitmap, and actual framebuffer/submission as separate critical prerequisites in the [next behavior plan](../architecture/simulator-next-behavior-plan.md). |
| Medium: changing observation already changes execution | Maintain pinned observation and prefer reading additional diagnostics after stopping. Do not report an event-prefix match as full state/timing equivalence. |

The SRAM MVA implementation's 32-bit range, ignored low five bits, set/way initialization, and counter separation are consistent in code; the review found no critical semantic error. This does not verify the physical cache or DMA.

## Workflow changes

Introduced `run_native_candidate.py` and a JSON plan that specify component SHA before and after a new candidate, pinned firmware/image, and runtime edits. The current cache candidate is `tools/sram-cache-candidate.json`. Add data for new scenarios instead of rewriting all historical tools. Do not silently update historical inputs to the current model.

For subsequent UART work, group the contract into one flow: transfer readiness → configuration → start → byte delivery → completion/IRQ or peer boundary, rather than splitting each register into separate work. Continue rejecting unsupported success responses. Keep normal-display asset research alongside this flow in the [plan](../architecture/simulator-next-behavior-plan.md) so it is not obscured.

Private `simulator/astra-direction-review-01/report.json` confirms successful re-audit of four existing main cases, unchanged input/log hashes, no native rerun, and reuse of the 51 cache unit results. New candidate source hashes are in `reflection-source-hashes.json` in the same folder. Product progress, scope, and completion judgment were not changed.

The post-review cache integration results, six regressions, and 54 audit checks are recorded in [cache model results](../hardware/cpu-memory/dcache-address-model.md). The existing 53 HCPA audit checks also passed again in `uart-hcpa-gate-verification-02`. This review request is complete; it distinguishes bw229's limited execution progress from the incomplete overall product.
