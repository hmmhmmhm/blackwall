# Pending Metadata Write and Next Boot Selection

2026-11-17 · bw-0573. **Under the declared 16-byte virtual ROM contract, the original pending clear → software POR request → new boot selection using the actual resulting state was confirmed.** Together with existing cleared/corrupt marker evidence, this completed BV02's virtual scenario conditions: 9/12 = 75.0%. This is not actual Boot ROM execution, silicon POR propagation, installation of a complete valid OTA image, or physical recovery validation.

## Model and original-execution boundary

Initial metadata is a distinguishable synthetic input, 55555555 + A5×12. Only the key 12344321/op 1/source 20022d68/offset ff800/four words/PRIMASK 1/FF×16 observed in the prior [actual ROM request](../bootloader/pending-boot-rom-request.md) is accepted. Original reset, RTOS work, original alignment/IRQ/power, ROM wrapper, subsequent MRAM control, and original SWPOR store execute as ARM. Only the ROM primitive is a functional model modifying this 16-byte owner; the existing read-only default remains.

A backend trap (BKPT) is mapped instead of original ROM bytes, but is not executed. Entry to the pinned Renode PC hook is a zero-instruction block, and the model accepts only this boundary at 0200ff20. It does not report success if actual instruction count is positive or ABI, range, source, or power differs. Other boot/main/MMU/ITCM protection logic was compared with frozen source and found identical apart from whitespace/comments.

The previously verified MRAM control object was connected opt-in to the shared 40014000 owner. It handles the three original subsequent key C3/config 0/key 0 writes without permitting arbitrary bits or addresses. Only with explicit binding does the reset controller accept 40000008/D4, **record the original POR request, and stop the CPU**. This is not actual POR. After the host pauses the machine, it passes the exported 16 bytes to a separate new virtual board. The new board runs the original reset from the existing cold profile; it does not reproduce actual device retention or the Boot ROM stage.

## Results of nine actual runs

| First run | State change and termination | New boot using the resulting state |
| --- | --- | --- |
| Success | Four words FF written; original IRQ restoration and POR request | Cleared branch → original handoff/main, zero ROM calls |
| ROM status 7 | Zero words; original does not check error and requests POR | Pending again → ROM error → POR request, state unchanged |
| Interrupted after zero words | Stops in ROM; no return/POR, state unchanged | Pending again; next success yields 16 bytes FF and POR request |
| Interrupted after one word | First word FFFFFFFF only, remaining 12 bytes A5; no return/POR | Enters main, zero ROM calls; remaining 12 bytes remain A5 |
| Power stuck | Stops at ROM boundary without readiness; no change/return/POR | Separate reboot not repeated |

On normal and ROM-error return paths, original SWPOR store PC 42e87c, stop PC 42e87e, PRIMASK 0 at request, and three MRAM control operations were confirmed. CPU faults, memory-policy violations, and peripheral guard failures were zero across all runs; original boot/main SHA values were unchanged. ROM interruption is a declared virtual fault at an atomic 32-bit word prefix, not the bit-level effect of actual power loss.

**A one-word partial write alone exited the pending branch.** This agrees with the original first-marker-word decision and actual execution. It does not guarantee that all 16 bytes were cleared or that remaining fields are safe. A5 is a synthetic initial value; no inference is made about actual adjacent 12-byte values or their purpose.

The two ROM-error reboots each re-executed pending → ROM error → POR with unchanged state. This is a finite two-run observation, not validation of an infinite loop on hardware. Raw CPU/GPR, event, fault, and guard results matched, but final elapsed ticks differed: 5409300000/6000200000. Other virtual peripherals can progress between CPU halt and host Machine.Pause. The first audit's whole-JSON exact check failed on this field and was retained; the final audit verifies agreement of the other raw facts without claiming time accuracy. Do not use this as a performance or POR-time measurement.

## Scope of BV02 completion

The original cleared branch was confirmed in the new boot following this success; pending success, failure, interruption, and termination were confirmed in the nine runs above. For corrupt marker 55555554, pinned report SHA, source, and main-entry evidence from the [earlier bw554 actual run](../bootloader/bootloader-validation-results.md) were reused. The original also handled this value on the normal main path; do not describe it as safe rejection of corruption.

This is **marker selection and termination/boundary classification** under the existing baseline NOR/virtual peer and declared metadata/ROM contract. It does not complete full interpretation or installation of a new valid OTA payload, actual ROM permissions, silicon POR, or installation certification per device version. Distinguish this scope from physical exclusions and other remaining conditions in the [full 12 conditions](../bootloader/bootloader-validation-plan.md).

## Initial failures, audit, and cleanup

- Thirteen pure C# conditions for metadata ownership/copy, partial writes, invalid inputs, and preservation across volatile reset were confirmed RED → GREEN.
- Initial native01 failed before guest startup because of a harness error querying the `@none` marker as a sysbus child. It was corrected to use the shared metadata owner's actual OtaMarker reference.
- Native02 stopped safely on a block-length-one assumption; diagnostic03 confirmed the actual length was zero. Run 04, which allows only the pinned engine's zero-instruction hook boundary, was used for the final nine runs. Do not classify this as original firmware failure.
- The time-exact failure from `pending-metadata-cycle-audit-bw573-01` was retained. `-02` and the post-cleanup frozen-source reaudit `-03` outside the repo under `/tmp` passed 105 conditions. Eleven existing boot runner unit tests also passed.

Outside Git, `simulator/pending-metadata-cycle-bw573-01..04`, `pending-state-{red,green}-bw573-01`, and the audit folders retain source/hashes, original inputs, native logs, actual before/after 16-byte state, parent-state lineage, initial failures, and audits. Termination of 14 owned native processes and absence of containers were confirmed; 86,749,067 bytes of duplicate main/guest image dumps were cleaned up. There were no new host compiler/cache outputs. Firmware and device secrets were not added to Git.

## Reproduction

Existing pinned private inputs and a Renode image are required. Use a new output name.

```sh
bw_assets="$HOME/Library/Application Support/Blackwall"
python3 -B tools/run_pending_metadata_cycle.py "$bw_assets/simulator/pending-cycle-new-01/success"
python3 -B tools/run_pending_metadata_cycle.py "$bw_assets/simulator/pending-cycle-new-01/reboot" --initial "$bw_assets/simulator/pending-cycle-new-01/success/exports/metadata-after.bin"
python3 -B "$bw_assets/simulator/pending-metadata-cycle-audit-bw573-03/audit-source.py" "$bw_assets/simulator/pending-metadata-cycle-bw573-04" "$bw_assets/simulator/pending-cycle-audit-new-01"
```

For errors and interruptions use `--fault rom-error`, `interrupt-0`, `interrupt-1`, or `stuck`. There is no configuration or physical-write capability. Continue BV05/06 same-board authentication/recovery and BV12 version-combination validation.
