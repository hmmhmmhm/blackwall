# Original OTA Marker State Transitions and Installation Gate

Task bw-0281. Address `0x7fe000` at the [boundary after record load](../hardware/cpu-memory/keydb-record-load-transaction.md) was analyzed using original code and saved context. **Startup requests a marker clear, but when the value differs it prepares a 16-byte write, not a four-byte write.** The actual marker and neighboring data are unknown. No device, MRAM, OTA, or new native main execution was performed.

## Code identification and scope

| Image | Startup read | Setter | Direct caller setting pending |
| --- | --- | --- | --- |
| Stock 2.4 | `0x44ac6c` | `0x483708` | `0x448c96` |
| Stock 2.3 / Faceclaw 38 | `0x44a962` | `0x480d54` | `0x448bde` |

An original string identifies the setter as `OTA_FileSystemSetBootloaderFlag`. A direct BL search in pinned Thumb decoding found two callers: setting pending and startup clear. PC-relative literal searches found the address in the startup read, setter, and application-range check. These searches do not prove the absence of indirect calls or calculated addresses.

## Differences in startup state

The startup function initializes a 96-byte state structure and reads the marker. It calls the version function and event logger only when the value is `55555555`. It then requests `setter(ffffffff)` regardless of that branch.

| Current marker | Startup pending branch | Operation prepared by clear setter |
| --- | --- | --- |
| `ffffffff` | Skipped | MRAM program skipped because value matches |
| `55555555` | Executed | Prepare 16-byte clear write |
| `00000000` | Skipped | Prepare 16-byte clear write |
| `12345678` | Skipped | Prepare 16-byte clear write |
| Unknown | Defer judgment for both real and virtual state | Do not automatically allow supplying a value or writing |

Thus `value != 55555555` is not a safe no-write condition. The equal-value branch and pending check are different conditions. A clear request during main initialization does not mean the full app loop, display, or CFW functionality booted successfully.

## Exact setter write footprint

The setter skips writing if the existing and requested words match. Otherwise, it copies a 16-byte all-ff ROM template to the stack and replaces only the first word with the requested value. Prepared call arguments are the normal program constant `12344321`, that buffer, destination `7fe000`, and four words. The test stopped before the MRAM callee call.

- Clear: 16 bytes of `ff`.
- Pending: little-endian `55 55 55 55` + 12 bytes of `ff`.
- Arbitrary request: requested word + 12 bytes of `ff`.

This is not a patch that reads and preserves the neighboring 12 bytes. Their purpose, preservation of originals, and suitability for the hardware/boot combination need separate confirmation. Backing up only the four-byte marker does not preserve the full write footprint.

The setter follows a diagnostic branch when the MRAM program result is nonzero, but neither of the two inspected direct callers immediately checks the setter result. This is not evidence of integrated execution of actual writing, readback, and error propagation. This local source result means completion of a raw caller alone must not be treated as successful marker application.

## Pending-path logging and reset limitations

The startup version function parses a source string into a packed 32-bit word. The following results were confirmed using the actual original function and initialized native SRAM:

| Image | Source string | Packed word |
| --- | --- | --- |
| Stock 2.4 | `2.4.0.24` | `02040018` |
| Stock 2.3 / Faceclaw 38 | `2.3.0.24` | `02030018` |

This word is passed as one argument to event ID `70108`. The internal logger reflects the count in record length in four-byte units. The version parser and argument preparation were checked; the logger's complete persistent-storage result was not verified. This is **main's version string**, distinct from the BLE controller version in the earlier `00402000` read and Faceclaw patch revision 38. Stock and Faceclaw have the same source string, so this value alone cannot distinguish stock from custom.

The caller setting pending passes `55555555` and continues into subsequent OTA state processing. The inspected later function is source `_RPC_SystemOtaStatusSync`, leading to transmission of an eight-byte opcode 103 message. This local path alone does not confirm CPU reset, bootloader execution, or application of new firmware. The complete updater/phone/case/boot reset handshake remains incomplete.

## Log read scope before supplying real data

Before the equality comparison, the setter calls a 32-byte hexdump function named `ota flag`. The original helper's gate checks an initialization byte, level, and filter. In the saved native context the level is 3 and the helper's minimum is 4, so the memory dump is skipped under those conditions. The next virtual marker model can therefore be limited to four bytes, but if verbosity changes and enables the dump, unknown adjacent data must remain blocked. Do not fill 32 bytes arbitrarily as though original just to make logging convenient.

## Source tests and input-error correction

`tools/inspect_ota_marker_contract.py` checks 21 conditions per image: four startup markers, 12 setter equalities, three 16-byte payloads, one program argument, and one full version parser. Across three images this gives **63 original ARM scenarios**. They use synthetic marker/stack/register inputs and M7 and execute the setter's actual memcpy, but do not execute MRAM programming, the logger, or full update/reset. There are no success stubs, forced branches, or write observers.

The first full version-parser test failed with a PC 0 fetch because the C-library callback was uninitialized in synthetic zero SRAM. This was not reported as a firmware defect. After replacing the input with a hash-verified full native-main SRAM snapshot, all three parsers returned normally. No fallback callback or return value was fabricated. The parser input SRAM hash was recorded in the report, separate from the explicit synthetic inputs of other branch fragments.

Private `ota-marker-contract-01` contains the initial 63 conditions; `-02/report.json` is the authoritative version including native hexdump gate state; pinned reanalysis `-03` retains source, caller, payload, snapshot pins, and conditions. `ota-marker-verification-01` pins dependencies, current web-gate source, input-error notes, and existing model equivalence. Original main/SRAM are outside Git; actual markers and secrets were not collected.

## Current installation and recovery gate facts

The current local `web/artifact-catalog.mjs` returns `installable:false` for every inspection result. `executeInstallation` in `web/installation-flow.mjs` checks this before Bluetooth selection. This is a source-supported complete block. **It does not mean a dedicated hardware gate validating marker-specific freshness and provenance has been implemented.** The pending/unknown stop requirement from the existing [recovery owner investigation](../bootloader/recovery-owner-flow.md) remains.

Current principles:

- Unknown, pending, or nonstandard values do not justify running a physical writer.
- `ffffffff` alone does not prove installation approval, compatibility, recovery capability, or freshness of the current state.
- A future dedicated gate must bind exact state, readback, and footprint from approved per-device checks to the operation. Do not create a path where a user enters hardware readiness through a UI number or checkbox.
- Do not equate upstream recovery's warning-only pending handling with Blackwall's write-authorization policy. The blocked catalog was not changed to installable here.

The next implementation is to retain unknown by default while providing explicit virtual cleared/pending marker reads, and verify the original clear/no-write and write-preparation branches separately. Do not extend that claim to MRAM writes, logger side effects, or reset support. Overall completion remains 13/29 = 44.8%; main/display and physical-device recovery remain incomplete.
