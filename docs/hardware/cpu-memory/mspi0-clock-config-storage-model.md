# MSPI0 Shared Clock, Configuration Storage, and Natural Execution

bw-0306. Connected the [original clock and initial configuration contract](mspi0-clock-config-contract.md) to natural M55 execution. No physical glasses or case were accessed; original main bytes, branches, and function return values were unchanged.

## Implementation scope and compatibility

Added `mspi0Storage` to the existing shared register object in `BlackwallMspi1ClockStorage`. Only when selected can MSPI0 bits 0–4 and source 7–10 be changed. MSPI1 and other channel fields are preserved; writes changing both channels simultaneously are rejected. Omitting the option preserves the existing MSPI1-only allowed scope. This does not model clock output, frequency, or switching time itself.

Extended the configuration class to specify base address `0x40061000` or `0x40060000` without duplicating register definitions. The default is MSPI1. MSPI0 uses a separate instance and dictionary and permits storage of only 25 verified configuration registers. PIO, XIP backing, IRQ, queue, and DMA execution options are rejected. Guest configuration access is accepted only while the selected MSPI0 power owner is on.

The startup fixture validates and separately connects the MSPI0 base and power owner. Existing class names and interfaces remain for compatibility. MSPI1 NOR/retention assumptions were not applied to MSPI0.

## Natural original execution results

| Condition | Clock/config access | Next strict boundary |
| --- | --- | --- |
| Stock 2.4 / active | source 10 and enable; 13 reads/20 writes | `0x572bae`, `0x400602c0 = 0` |
| Stock 2.3 / active | Same | `0x555c5a`, same |
| Faceclaw 38 / active | Same | `0x555c5a`, same |
| Stock 2.4 / stuck-off | source 8 and enable; zero config reads/writes | `0x4e7186`, `0x40060090` read |

The three active inputs passed original clock configuration and uLED initial configuration to the first command-queue `CQCURIDX` write. Original `str r0, [r3]` and actual register arguments were compared. Queue execution, DMA, PIO transfer, and IRQ completion had not yet been generated. Clock source 10 and enable are register states, not a measurement of actual 250 MHz output.

In stuck-off, the original also wrote the clock first and attempted to read configuration, but the virtual bank's power condition rejected the first read. Original `ldr r5, [r4]`, target `0x40060090`, and zero configuration-bank accesses were confirmed. **A virtual model blocking access differs from a safe firmware error fallback.** The latter was not established. Event equivalence is not claimed on the timeout path; separate invariants, inputs, and stop points were checked.

The default unselected control retained the prior MSPI0 clock-write boundary, with CPU, instruction count, and all events exactly matching the earlier execution. Existing BLE 59 instructions/60 responses remained in all conditions. Stuck-off combinations for older stock/CFW were not run in this work.

## Verification and preservation

- Preserved the red failure for the missing new argument. Passed 33 unit checks and frozen reverification. An initial harness error in the clock-object path was also preserved separately.
- Strengthened the simultaneous-channel-change negative input so each channel's individual value is valid; reverified the 33-case frozen suite. Preserved prior suite, dependency pins, and execution inputs without rerunning native main.
- Passed 16 existing MSPI1 clock and 67 configuration regression checks. Checked default clock mask, base address, and allowed/blocked behavior.
- Five natural native runs and five saved audits. The first four candidates failed because expected bounded idle differed from the actual strict boundary; original reports were retained. They were verified with separate saved audits.
- Repeated saved analysis using 78 pinned Python dependencies; report and inspector matched byte for byte. Three model sources changed—startup core, clock, and configuration—and six other optional models' hashes remained unchanged.

Tools: `prepare_mspi0_config_candidate.py`, `inspect_mspi0_config_profiles.py`, `verify_mspi0_config.py`. Pinned evidence: `private:simulator/mspi0-config-peer-verification-01/manifest.json`. Proprietary originals, RAM, and execution logs were kept outside Git.

Next combine nonexecuting queue initialization, IRQ enable/clear, and retention-power paths and compare them with original and public register contracts. Do not supply arbitrary completion/idle values to report queue or display success. Integrated framebuffer, display transfer, viewer, and full boot remain incomplete; scope v2 remains 13/29 = 44.8%. The web installer, recovery boot, and installation CFW were unchanged by this work.
