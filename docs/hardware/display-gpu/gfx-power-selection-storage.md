# GPU power selection and performance-request storage model

Status: limited verification completed for native model, 15 synthetic conditions, three existing-behavior regressions, and six actual main combinations. Full boot, GPU rendering, and integrated screen remain incomplete.

## Evidence and scope

Pinned Ambiq HAL `61b293a49db34030c545f99101f7ebf6a3050314` `am_hal_pwrctrl_gpu_mode_select` checks that GPU is off and SIMOBUCK ACT before HP selection. It selects supply and stores performance request after a delay. Current model can be selected only under existing startup-controls peripheral-off assumption; this does not mean device or bootloader actually supplies that initial state.

Public `apollo510.h` and `pwrctrl_regs.html` define:

| Address | Register | Supported behavior |
| --- | --- | --- |
| `0x40021090` | GFXPWRSWSEL | bit 0 supply selection, public reset=0, VDDC=0/VDDF=1 |
| `0x4002108c` | GFXPERFREQ | bits 1:0 performance request, public reset=0, LP=0/legacy HP3=3 |

GPU HP1/HP2 request values 1/2 are also public-header values, but this model is limited to pinned HAL legacy LP/HP branches and stops them as unsupported. Reserved bits, partial widths, and neighboring addresses also stop. HP3 requires source 1/buck ACT; LP requires source 0. Repeated requests are field storage. These are virtual-model scope restrictions, not a claim physical hardware rejects all other sequences.

`tools/renode-strict-mmio.cs:BlackwallGfxPowerStorage` preserves only two fields and access counts. It does not model voltage, settling delay, GPU clock/commands, framebuffer, or performance. Execution of original delay instructions does not establish physical voltage stabilization.

## Execution and boundary

Select `tools/run_renode_main_probe.py --gfx-power-storage` with existing startup-controls and clock-response assumptions; default is disabled. Option binding is confirmed in actual reports and unsupported accesses retain existing first-access stop policy.

Python approximate runner stops at earlier SHCSR/MPU boundary. This stage connected to M55 main runner; no approximate implementation of the same peripheral was added to extend both runners. No claim of identical full CPU/board models.

All six combinations stored source 1/request 3 once each and stopped on `CLKGEN.MISC` (`0x40004044`) bit 0 FRCHFRC set write (`0xfbbfc1`). Stock 2.4 PC `0x506e66`, stock 2.3/Faceclaw `0x4e85da`. This subsequent HFRC behavior remains unsupported.

`compare_dcache_startup.py --buck-response active --mcu-clock-response nominal --gfx-power-storage` checks native field state and subsequent write. Python SHCSR and native endpoints differ. Native additionally executes geometry/selector once each, 2,048 clean-invalidates, buck reads 2, MCU mode reads 2 relative to Python. Common state excluding these differences is compared; full execution equivalence is not claimed.

## Evidence

- Private `simulator/gfx-power-native-guard-01/report.json`: 15 conditions passed. Four normal observations wrote completion sentinel; 11 rejections stopped at first unsupported access without completion write.
- `simulator/gfx-power-verification-01/main-prefix-audit.json` and each `*-gfx-prefix.log`: actual GPU RMW static disassembly after input bundle SHA/component CRC verification.
- `simulator/gfx-power-main-stock24-lp-01/report.json`: first original main run and next stop, reused in subsequent six-combination comparison after source/hash/option verification.
- `simulator/gfx-power-main-comparison-01/report.json`: limited verification passed for two stock versions and Faceclaw × LP/HP six combinations.
- `simulator/gfx-power-native-regression-01/report.json`: three default unsupported read and existing nominal/no-ack clock response cases passed.
- `simulator/gfx-power-source-audit-01/report.json`: public addresses, reset, field masks, compiled C structure offsets, and textual HAL processing order. Reproduce with `tools/verify_gfx_power_sources.py`.

Initial unimplemented `gfx-power-native-red-01` timed out 45 seconds after platform load. Expected failure state was not observed, so it is not counted as valid red. Its own container was cleaned before separate verification with implementation source. Running test source was not changed.

No actual glasses access, OTA, MRAM writes, GPU driver implementation, or external publication.
