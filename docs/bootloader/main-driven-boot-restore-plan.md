# Verifying full boot restoration through original main

2026-11-17 · bw-0571. Targeting the existing virtual-original 4 MiB, sequentially process 39 pages of boot footprint 410000..437000 with the original callback and original OTA verifier. The synthetic SRAM caller handles only function calls and progress control; copy/compare algorithms run in original main. ROM programming is an explicit functional model.

The default 4 KB scope remains. Separate --boot-restore is allowed only with callback+ota+chip/delay profile, and ROM rejects anything except 39 consecutive 4096-byte requests with corresponding sources. Observe actual return, IRQ, and original readback buffer at caller's page_verified point. Original main/IRQ/power/callback and cache reset profile match bw570. This is not physical ROM or natural BLE OTA.

Connect actual MRAM verified for all 159744 bytes, 39 original verifications, full 4 MiB hash, and unchanged adjacent regions to a new stock boot reset→main/frame. Synthetic-original boot tail 0 is not a physical backup. BV11 is not completed before all changed persistent components match the virtual original and a new boot passes. After independent audit and default-scope regression, clean duplicate builds/dumps. No physical device, external publication, or Astra.

Configuration-scope RED was confirmed by TypeError for unimplemented boot_restore argument; five GREEN checks passed. Original functions/returns are not replaced with success.

Result: [full MRAM match, new boot/display, audit and cleanup](main-driven-boot-restore-results.md). BV11 virtual condition complete, overall 8 of 12. Original ROM, natural BLE OTA, and physical certification remain incomplete.
