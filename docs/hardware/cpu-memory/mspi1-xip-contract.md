# MSPI1 NOR/XIP boundary investigation

Conclusion: Strong code evidence indicates that the current main's MSPI1 initialization caller is a **NOR flash driver path**. The requested aperture is `0x80000000–0x81FFFFFF`, 32 MiB, read-only. The actual flash chip, contents, and capacity, and successful XIP reads or execution have not been established.

This stage analyzed static and saved evidence. It did not change the production model or execution endpoint, and retained the existing block on DEV0XIP write `0x5ED`. No new guest execution of the two stock versions or Faceclaw, or physical-device access, took place.

## Findings in the original

The main bytes, asset hashes, and raw logs/reports of the three pinned `mspi1-cq-init-main-01` inputs were rechecked.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw |
| --- | --- | --- |
| PC stopped at XIPEN write | `4E7EC0` | `4DAAEC` |
| Caller return pointed to by LR | `47B0CE` | `4763B6` |
| Control callee of preceding BL | `4E7824` | `4DA450` |
| Configuration constant object | `7AF724` | `7BDA8C` |

The original current instructions are `ldr` → bit 0 OR → `str`, and the intended write value is `0x5ED`. The saved configuration marker shows DEV0XIP `0x5EC`, DEV0AXI `0x19`, and DEV0INSTR `0x006B0002`. XIPEN=1 was only attempted; the model rejected it.

Static log literals in the caller region point to `driver/flash/drv_mx25u25643g.c` and `am_devices_norflash_qspi_init`. This does not mean the log was actually printed. The BL corresponding to LR and literals in that region were checked together, providing strong evidence for the NOR initialization path over the earlier panel-driver candidate. This does not establish that an MX25U25643G is installed in the actual device. The binary also contains strings concerning GD25LE256H and an unknown-ID fallback.

## Address window and ABI

The 16-byte configuration constants are identical across the three inputs. The first two words are 0, the base word is `80000000`, and the last word is `00000901`. Original control code uses **byte loads** for mode at offset 12 and size at offset 13. These correspond to mode 1/read-only and size 9/32 MiB, consistent with the dynamically saved DEV0AXI `19`.

This is evidence from the constant object, a 16-byte copy request, and static byte accesses. The current inspection did not establish that the entire 16-byte copy completed in live RAM.

`am_reg_base_addresses.h`, `am_hal_global.h`, and `am_mcu_apollo.h` from public HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` were pinned by SHA-256/Git blob. Existing MSPI/header pins were also rechecked. The documented full MSPI1 window is `[80000000,84000000)`; the currently requested size is the first 32 MiB within it.

The separate legacy constant `MSPI1_XIP_BASEADDR=08000000` or convenience macros in the public header are not copied as the current mapping. The basis is the agreement between the HAL range check directly using `MSPI1_APERTURE_START_ADDR=80000000` and the original range-check instructions and configuration object.

M55-targeted C compilation verified two layouts:

- Default enums: 20-byte structure, mode offset 12, size offset 16.
- `-fshort-enums`: 16-byte structure, mode offset 12, size offset 13.

The latter reproduces the observed byte-access layout of the original, but does not prove the original compiler flag. Nor does it mean that the entire public SDK structure or enum ABI matches G2. Together with the previously observed peripheral enum number differences, this is why exact-image verification is needed.

## Backing and conditions for the next implementation

Read-only is an **AXI aperture configuration**. It does not mean the entire NOR is immutable or that other PIO/DMA/OTA writes are prohibited. The 32 MiB is also the requested window size, not an identification of physical capacity.

`mspi1-xip-contract-05/required-backing.json` records:

- Base `80000000`, size `02000000`, end-exclusive `82000000`.
- No known data ranges. The entire 32 MiB is unknown.
- Original backing image and SHA-256 are null.
- Unknown reads must stop; they must not be filled with 0/FF.

The next step is to connect the source-backed address window and a strict access guard, then identify addresses actually read and the required backing sources. Do not treat the original main binary as a NOR image or invent unverified font/filesystem data to pass boot. External code execution must be verified separately under the existing executable-memory policy. This investigation does not authorize hardware dumps, RAM execution, or persistent writes.

## Verification record

Contract05 in `tools/inspect_mspi1_xip_contract.py` passed 58 source/asset/runtime-context/static-ARM/layout checks. Source, compile logs, report, and backing requirements are in `simulator/mspi1-xip-contract-05` outside Git.

The initial contract01 failed extraction because of a line break in the enum typedef, and contract02 failed because it fixed the literal-load destination register to r1. These were corrected by allowing whitespace and supporting actual r2/r3 literals, respectively. After contract03's 49 checks, direct BL and copy-length 16 checks were added for 55 in 04; saving and checking the original module 1's 80000000/64 MiB range-check instructions brought 05 to 58. Failure evidence was preserved; the guest was not restarted and the model guard was not relaxed.

A review by an agent inheriting the parent model found no significant errors; its distinction between the static object, live RAM copy, compiler flag, and physical chip was incorporated. Astra, another model-family review, and a full transcript archive audit were not performed. Full boot, application loop, integrated screen, and physical-device recovery remain incomplete. Product completion remains 13/29, 44.8%.

Follow-up bw163 connected [guarded XIP control](mspi1-guarded-xip-control.md). It records enable requests after configuration validation, but stops unknown reads/writes in the module window. This does not mean backing was obtained or flash reads succeeded.
