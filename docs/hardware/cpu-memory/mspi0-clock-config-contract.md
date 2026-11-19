# uLED MSPI0 Clock and Initial Configuration Contract

bw-0305. The original stack frame from the [natural MSPI0 power run](mspi0-shared-power-model.md) identified the upper caller as the initialization path in `drv_mspi_uled_common.c`. The display role was established by comparing the actual frame, BL instructions, and diagnostic strings, rather than inferred from a generic MSPI library address. No new native main run or model change was made.

## Shared clock register

The fixed SVD/header and SDK commit `61b293a49db34030c545f99101f7ebf6a3050314` were verified. In `CLKGEN.MSPIIOCLKCTRL(0x40004110)`, MSPI0 enable is bit 0 and source selection is bits 1–4. Source enums 7/8/9/10 designate nominal HFRC 96/192 MHz and HFRC2 125/250 MHz, respectively. Actual output frequency and delay were not measured.

The existing clock model can modify only MSPI1 bits 5–9 in this shared register. Duplicating the MSPI0 region as a separate register object would split the two channels' state, so the appropriate approach is to add MSPI0 fields optionally to the same storage object. The default option must retain the existing MSPI1 scope.

The original clock helper selects the source and enables it in two writes. The first source 8 write, `0x0a4210`, still has enable=0; the next write is `0x0a4211`. The isolated execution stopped at the original delay call after enable. It did not skip the delay and execute subsequent code or force a clock-ready return value.

Each image was run under eight conditions combining two existing shared states with sources 7–10, and two source-preserving enable and disable conditions. The other MSPI channel fields were preserved. The disable case ran until the helper returned, but did not verify actual peripheral power-down.

## Initial configuration and subsequent boundary

The original uLED initialization order is MSPI handle preparation → power → TCB configuration → device configuration → enable → interrupt configuration → power-state change request with a retain argument. The later steps were confirmed statically from BL instructions and arguments; they were not completed in a natural run. The retain request has state argument 2 and retain argument 1. The current MSPI0 power model does not yet support this shutdown and retention path.

The handle, TCB buffer, and device descriptor in the original frame were reconstructed from hash-verified full SRAM. The assumption that the TCB base structure could be read from ROM alone was rejected, and the alternate-clock flag was verified in the actual SRAM template. The flag was 0 in all three images. The failed evidence and the tool before correction were also preserved as private research assets.

| Isolated run | Observed behavior | Completion scope |
| --- | --- | --- |
| TCB configure | Clear bit 0 of DEV0XIP; store 0 for SCRAMBLING and AXI configuration | Function returned 0 |
| device configure | Disable existing MSPI0 clock → request HFRC2 force → select source 10 → enable | Stopped immediately before the original clock delay call |

The HFRC2 ready input for device configure is an explicit virtual condition taken from the HP mode and nominal clock responses in an existing native run. It is not generalized to actual device oscillator readiness or switching time. The complete device configuration function return and subsequent MSPI enable, IRQ, DMA, PIO, and lens output were not executed.

The existing MSPI1 configuration bank's **25 register offsets, resets, and masks** matched the MSPI0 SVD. This supports reuse of the limited configuration storage, but not copying MSPI1's NOR peer, XIP backing, PIO completion, or retention power assumptions to MSPI0. Addresses and owners must remain distinct, and unselected features must remain blocked.

## Verification and traceability

- Three images × (10 clock + 1 TCB configuration + 1 device configuration delay boundary) = 36 original ARM fragments.
- TCB configuration was executed separately with an MMIO callback and an ordinary memory backend; full SRAM, WORK, ordinary registers, XPSR, PRIMASK, and the PC path matched. No SRAM write hook was used. This match does not guarantee that every other function or observer is unaffected.
- A repeat with 73 frozen Python dependencies produced byte-identical report and inspector files. The hashes of nine selected model sources were unchanged; the clock/config source was also verified to appear once each in the compiled sources of the three native captures.
- Unsupported clock reads, MMIO callback exceptions, and an isolated runner's failure to access the delay during initial exploration were preserved. The final analysis uses the original delay call as an explicit termination boundary and does not use failed exploration guest state as subsequent input.

The tool is `tools/inspect_mspi0_initialization.py`; evidence is in `private:simulator/mspi0-init-verification-01/manifest.json`. Original ARM code ran in Unicorn M7 using synthetic function entry, stack, and manual register fixtures. This is distinct from natural M55 boot and real-device verification.

Integrated display condition D3 changes from **pending → partial**, based on identifying entry into the uLED driver initialization and the clock boundary in the original natural main run. Framebuffer, stride, transmission, and the 576×288 viewer connection remain incomplete; logical HUD dimensions are not equated with raw panel dimensions. Completion criteria and denominator are unchanged, retaining overall scope v2 at 13/29=44.8%.

Next, optionally connect the same clock storage object and limited configuration bank to MSPI0 and use an original natural run to check subsequent configuration, IRQ, and retention power boundaries. The web installer, recovery boot, installation CFW, and actual glasses were not changed in this work.
