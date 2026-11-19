# Draft Recovery Patch Compatibility Inquiry

Status: The user decided not to send this inquiry. Preserve the unpublished draft for reference and exclude it from pending approvals. Continue with direct analysis of firmware versions.
Intended destination: https://github.com/drdaeman/g2-bootloader-patch/issues

## Title

Pre-install identification and Faceclaw coexistence on G2 main 2.4.0.24

## Body

I'm evaluating a recovery-first setup before making any changes to my G2. The official app reports main firmware 2.4.0.24 and model S211; the actual bootloader hash, hardware revision, and case firmware are still unknown. No hardware flashing or RAM payload execution has been performed.

I inspected g2-bootloader-patch at 6198d70e18293caebf8314d2e40bd3b1d0a5ee16 and g2flash at 845f665e0dfdcfd06b7d3a294388de6f17a5bd59. The patch accepts the 2.3.2.14 stock bootloader hash, whereas the boot component in the official 2.4.0.24 bundle has a different hash. I understand that a distribution bundle does not establish what is actually installed on a device.

1. Is there a supported way to identify the installed stock bootloader and hardware revision before patch installation, without persistent writes or relying on an already-patched bootloader? Which values, if any, from the standard BLE Device Information Service are meaningful for this check?
2. Has the patched 2.3.2.14 bootloader been tested with Faceclaw/38's 2.3.0.24-based main firmware? If so, which hardware, case, and codec/resource versions were used? We would keep the main update separate from the boot component to avoid overwriting the recovery patch.
3. The README documents right-temple 1 KiB restoration tests and explicitly says full application replacement has not been hardware-tested. Is there newer evidence for full application recovery, or any additional prerequisites to preserve a reliable path back to stock main firmware?

I'm looking for existing evidence and limitations, not a guarantee of recovery. We are keeping installation disabled until the relevant compatibility and recovery questions are resolved.

## Record scope

The body contains no device-specific serial/MAC, recovery keys, or private firmware. Approval to publish would not authorize physical-device work.
