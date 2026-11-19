# Pending Metadata Functional Contract and Post-Reset Verification

2026-11-17 · bw-0573. The virtual ROM model handles only the actually observed request for 7fe000/FF×16/four words. The existing read-only marker default and frozen board are preserved.

- Metadata ownership/copy for 16 bytes, partial writes, preservation across volatile reset, and invalid-input rejection were verified RED → GREEN in 13 pure C# conditions. The initial 16 bytes are the synthetic distinguishing input 55555555 + A5×12.
- Execute the original boot IRQ, power, original ROM wrapper/post-control, and original SWPOR write. Connect only ROM entry 0200ff20 as an explicit callback in the memory policy, retaining all other existing code/MMU boundaries. The backend BKPT is a trap, not an original ROM instruction.
- Distinguish success, ROM error, interruption after zero or one word, and stuck; pass the actual changed 16 bytes into a new cold profile. Stop at the SWPOR request and restart in a separate machine; do not describe this as silicon POR/Boot ROM propagation.
- Connect the previously verified `BlackwallRecoveryMramControl` to the shared MRAM control owner only in the composite profile. Check the original subsequent write key C3/0 and config 0 unchanged. No arbitrary success return, original branch modification, or device access.
- The first native run failed before guest execution due to a harness registration error querying the `@none` marker as a sysbus child. It was corrected to use the actual metadata owner's `OtaMarker` reference, and the failure evidence was retained.

After verification, retain source, hashes, logs, 16-byte state, and audits, and clean up duplicate main/build outputs. BV02 remained partial pending completion and next-selection audit; overall progress remained 8 of 12.

The second native run had all correct arguments but stopped on an assumed block length of one. Diagnostics confirmed block instructions = 0 at PC hook entry. The guard was corrected to allow only this exact zero-instruction model boundary and reject ROM instruction execution. Initial failure 02 and diagnostic 03 were retained. Successful run 04 executed through original post-control, IRQ restoration, and SWPOR request, confirming 16 bytes FF, the control boundary, and zero guard failures.

Results: [Virtual marker lifecycle, POR request, and new boot selection: nine runs and audit](pending-metadata-cycle-results.md). BV02 virtual conditions were complete and overall progress was 9 of 12; actual ROM/POR propagation and a valid full OTA installation remained unverified.
