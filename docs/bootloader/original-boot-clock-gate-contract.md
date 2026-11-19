# Original boot clock gating and HFRC preservation

Status: bw531 in progress. Main and display integration remain incomplete.

The CLKGEN.MISC write at original PC 41c5c8 reads current 1, ORs fbbfc0, and clears AXIXACLKENOVRRIDE bit 14, yielding fbbfc1. The same operation in SDK `am_hal_pwrctrl_low_power_init` was compared against the pinned header. OR of 16 gate fields is fbbfc0 and excludes FRCHFRC/FRCHFRC2.

Existing HAL storage allowed 0/fbbfc0, and the clock model allowed only changes to force bits 0/5. Thus the original combined RMW was rejected by both paths. The clock model now additionally accepts only gate portion 0→fbbfc0 while exactly preserving existing force bits. GateWrites is recorded separately from ForceWrites, without changing existing phase or digital clock status. Arbitrary gate patterns, unsupported bits, and simultaneous force/gate changes remain rejected.

This is a storage model for a known gate configuration, not evidence of physical clock gating/PLL frequency, stabilization, power consumption, or accuracy of general gate combinations.

## Evidence and verification

- `private:simulator/boot-clock-gates-source-bw531-01/source-proof.json`: OR calculated from actual field masks in pinned HAL 2364–2384/header.
- `model.patch` and `change-proof.json` in the same folder: model change scope and SHA.
- `private:simulator/boot-clock-gates-red-bw531-02/report.json`: reproduced rejection of original-like force 1→fbbfc1.
- `private:simulator/boot-clock-gates-green-bw531-01/report.json`: 26 checks passed, including force 0/1/32/33 preservation, subsequent control, gate counts, and unsupported-input blocking.

Initial RED01 began with force 0 and failed at absence of the new GateWrites field after previous HAL storage accepted the gate value. It is not counted as reproducing the original symptom; actual write blocking in RED02 starting with force 1 is used as evidence.

## Original execution and cleanup

All ten existing clock regression conditions passed. The original executed 14,019,530 instructions and reached the next strict boundary reading CLKGEN.HFADJ (40004020) at PC 426fd8. Gate write passed, code/system protection and CFSR/HFSR errors were 0, and main/frame were not reached. Since original function 426fd6 is a path clearing HFADJ bit 0, initial register value and that field's preservation/blocking contract are investigated subsequently. Authoritative record: `private:simulator/original-boot-clock-gates-native-bw531-01/frontier-proof.json`.

Ten regression ELFs totaling 335692 bytes and an identical 149773-byte boot dump were cleaned up. Source, logs, pinned model, SHA, and reproduction commands remain; owned Docker removal was confirmed.
