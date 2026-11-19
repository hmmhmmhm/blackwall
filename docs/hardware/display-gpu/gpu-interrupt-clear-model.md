# GPU initial interrupt-clear model

Status: observation completed for 13 synthetic conditions and four actual main conditions. Full boot, integrated screen, and physical verification remain incomplete.

## Supported scope

`--gpu-interrupt-clear` requires an explicit GPU power response. It permits only idle IRQ clear by writing DWORD 0 to 0x400900f8 while GPU power phase is `on`. Repeated identical clears are allowed. Initial IRQ state is synthetic idle. It does not generate GPU command execution, completion interrupt, reset, or NVIC pending clear. Actual GPU IRQ-line to NVIC connection is not implemented.

The basis is pinned Apollo510 HAL in [GPU initialization research](gpu-initialization-research.md) and static initialization code in three images. GPU power off/stuck-off, reads, partial writes, nonzero values, and neighboring registers stop at unsupported guards. This supports only the observed zero write, not the entire public documentation's write-clear behavior.

The watchdog-separated high MMIO guard references the low guard's GPU control owner. Power state and clear count are therefore shared; no separate on state is created in the high guard.

## Verification history

- Pre-implementation probe timed out 45 seconds after system-bus creation. No guest failure was observed, so it is not treated as valid red. Preserved in `gpu-irq-clear-red-01`.
- Initial monolithic nine synthetic conditions passed. First actual main run was not connected to the high guard and stopped at the previous GPU boundary with clear 0. `gpu-irq-clear-main-stock24-lp-01` is connection-failure evidence, not a successful result.
- Tests after owner-connection correction are preserved separately. Final results follow.

This model does not verify official hardware IRQ timing, pending state, or power gating. No physical connection, installation, OTA, or MRAM writes occurred.

## Final observations

Final source `gpu-irq-clear-native-02/report.json` passed nine new conditions (two normal, seven blocked) and four existing power-response regression conditions. It distinguishes normal/repeated clear, read, partial write, nonzero value, neighboring register, stuck-off, unrequested, and option disabled.

Three LP/active runs of stock 2.3, 2.4, and Faceclaw stopped at GPU 0x40090148 DWORD 0 write after one clear. Writer PC is stock 2.3/CFW 0x530054, stock 2.4 0x560f68. The same writer helper is used, so the stop address changed even though PC matched the previous one. Public GPU documentation names offset 0x148 DRAWPT2Z, but that register's meaning was not yet modeled. No command execution or framebuffer generation was observed.

Stock 2.4 LP/stuck-off had clear 0 and was blocked at previous GPU 0x400900f8 write. This is simulator blocking, not proof of safe original firmware fallback/recovery. HP combinations were not rerun at this stage. Python runner retains the earlier SHCSR boundary.

Final native source snapshot and combined main source were checked against current files; results and hashes are preserved in `gpu-irq-clear-verification-01/final-verification.json`.

## Follow-up semantic research

[Ring initialization research](gpu-ring-setup-research.md) found a discrepancy between 0x148's public name and command-list handling code. DRAWPT2Z here is the public metadata name, not confirmation of coordinate-register meaning in the actual firmware path.
