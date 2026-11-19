# Virtual System Reset Foundation Contract

bw-0414. E06 is partially complete. Overall acceptance remains **8/16 = 50.0%**, and the first-screen checklist remains 3/6. This test uses a synthetic Cortex-M55 ARM guest; it is not evidence of original G2 firmware reboot. No physical-device access or subagent invocation occurred.

## Verified boundary

The same guest ELF was executed on pinned Renode 1.17.0 `f1dd1b4af7838b45a925c17603cdfed0a583844a` and infrastructure `cd4b002aac2398994c4a61a34a8b31b5700facf2`. Seven original-engine conditions were compared with seven opt-in NVIC model conditions. Each set comprises machine reset/guest AIRCR SYSRESETREQ × no mask/BASEPRI/PRIMASK, plus one condition missing initial-vector configuration.

- The guest sets BASEPRI or PRIMASK with MSR and records actual state with MRS. The guest AIRCR path uses an ARM instruction to write `0x05fa0004` to `0xe000ed0c`. Host PC or CPU register changes are not used as a substitute for reentry after reset.
- With initial vector `InitVectorTableOffset=0x438000`, the boot counter increases from 1 to 2. Setting only VectorTableOffset for initial execution fails at VTOR 0 after reset. A negative control mapping address 0 ITCM was retained.
- On the original engine, even after the guest BASEPRI value resets to 0, the NVIC cache remains 0x50 and the IRQ does not arrive. IRQ arrives in PRIMASK and unmasked controls.
- Separate `BlackwallResetAwareNVIC` clears the non-secure BASEPRI cache after base.Reset. Both reset paths confirmed cache 0, guest BASEPRI 0, IRQ consumption, and reboot. TrustZone profiles are rejected; this model was not connected to the existing G2 board or default engine.
- Guest source and ELF are byte-identical across both sets. ELF SHA-256 is `3c3381273afdc3de9261bf20e29bd6b5bab8e3b0608390e7739b3793ad86aa77`. Retained RAM cookie `0xcafebabe` also persisted. This is behavior of the selected mapped RAM model, not a physical SRAM retention guarantee.

This agrees with upstream [BASEPRI reset issue #1021](https://github.com/renode/renode/issues/1021) and [NVIC fix 6967961](https://github.com/renode/renode-infrastructure/commit/6967961967c4024d9918709e8a030e6b1944bc9c). The actual engine's submodule pin was checked separately; a different revision mentioned in the issue was not treated as identical source. Upstream source, Git blobs, and MIT materials are retained in the private research folder.

## Audit and failure history

Saved original-engine results passed 11 checks and opt-in results passed 12. The audit compares JSON reports, native logs, each run's ELF, and exact guest source. Three mutations reflecting missing IRQ, retained cache, or lost cookie in both JSON and logs, and one control classifying the original engine as the modified model, were all rejected. Fourteen progress-management regression checks also passed.

The first fixture failed to build due to lowercase REPL property spelling. Later, because the IRQ input was held at level, an audit expectation of exactly one ISR occurrence also failed when the ISR repeated. Inputs and execution logs were retained and the saved audit was corrected to check positive/increasing values. Failed executions were not turned into successes or reported as original G2 execution.

Evidence: private `simulator/system-reset-boundary-research-01/manifest.json`, baseline `system-reset-boundary-unit-02`, opt-in `system-reset-boundary-unit-03`. Initial failures are retained in `system-reset-boundary-unit-01`.

## Next integration work

E06 completion requires device reset during original E05 main execution and return to app state. First declare the reset domains. Current source shows NOR backing Reset retains data and PIO controller Reset clears an unfinished timer/FIFO/WEL, but this does not establish actual external flash warm-reset behavior. RTC Reset returns the date to 2000, so warm-reset retention needs a decision. Also inspect ITCM provenance in the memory policy and the lifetime of manually installed hooks and diagnostic state.

Then connect the declared domains to the original board opt-in and check actual guest reset request → vector reentry → service/app event reprocessing. Full app return, bootloader execution, and physical G2 reset causes and retained state remain unverified.
