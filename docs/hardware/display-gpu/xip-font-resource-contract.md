# XIP font assets and original failure path

## Conclusion

The `0x80100000` read where original main stopped after TIMER0 initialization is LVGL font initialization. Stock 2.4.0.24, 2.3.0.24, and Faceclaw 38 all reference the same two external font headers. Available OTA bundles have no independent font-bank component; a legitimate download URL, version, and hash for the actual external font image have not yet been obtained.

**Header error handling and a usable font fallback are different.** On magic error original code clears the descriptor and returns, but that font object's glyph-lookup callback does not safely reject ordinary characters when its descriptor is absent. Supplying arbitrary 0 or FF to the entire XIP region cannot be treated as a screen fix.

Work bw-0217. No physical access, firmware patch, or new XIP response model. Overall conditions remain 13/29, 44.8%.

## Contract confirmed in original code

`tools/inspect_xip_font_contract.py` verified three hash-pinned bundles and compared first stops of six existing low/high original main runs. Final 173-check source report is outside Git at `simulator/xip-font-contract-03/report.json`. Initial audit decoded a literal pool continuously as code and could not find the parent. Final tool finds a unique direct BL at neighboring aligned addresses and decodes only subsequent code. Failed `contract-01` is not completion evidence.

| Item | Stock 2.4.0.24 | Stock 2.3.0.24 / Faceclaw 38 |
| --- | --- | --- |
| Font initialization entry | `0x476040` | `0x471312` |
| First header read | `0x47605a` | `0x47132c` |
| Second header read | `0x476134` | `0x47140c` |
| First/second descriptor-clearing stores | `0x476130` / `0x4761da` | `0x471408` / `0x4714b2` |
| Initialization return instruction | `0x4761e2` | `0x4714ba` |
| Chain builder | `0x4758f0` | `0x470b58` |

Header addresses are `0x80100000` and `0x80700000`; magic is `0x5a5a5a5a`. The valid branch stores the pointer at header+`0x34` into font object+`0x18`. The 16-bit values at header+`0x38` and +`0x3a`, when not FFFF, are stored at object+`0xc` and +`0x10` respectively. First bank also has a 16-byte copy from header+`0x24` and internal descriptor references. Correct magic or a small header alone cannot form a valid font. Name at header+4 is used as a log string. Full asset format, length, and all pointer ranges remain undetermined.

The magic-error branch sets object+`0x18` to 0. After handling both banks original code calls a release function and returns r0=1. This return is not interpreted as successful font load.

Three bundles passed parser boundary/CRC checks and original main hash verification. Included components are codec, BLE, touch, box, bootloader, and main. This establishes absence of an independent font-bank component, not absence of all embedded fonts in main.

## Read-only RAM observation of original main

`tools/probe_xip_font_config.py` reran three images in existing low-role scenarios. Results: `simulator/xip-font-config-main-01/{stock24,stock23,cfw}/report.json`. Original main, board, and peripheral model were preserved; only four SRAM observation hooks added. Runs stopped at the same first XIP guard with all existing events, CPU registers, and other report state equal. No events lost.

Exact count difference: in all three, `ExecutedInstructions` increased by **1** from baseline. The tool explicitly checks and preserves it. It appears related to adding an observation hook at the faulting load, but engine-internal cause was not separately verified. Do not report identical instruction counts or completely identical instrumentation. Stock24's first audit rejected the difference; final audit used `--audit-existing` preserving inputs. That option does not restart execution.

Each chain has four 12-byte configurations. Observed first-byte types are all 0, with font-object pointers at +4:

| Image | First chain object order | Second chain object order |
| --- | --- | --- |
| 2.4 | `20002954`, `20002978`, `20005b30`, `200028e8` | `2000299c`, `200029c0`, `20005b54`, `200028e8` |
| 2.3 / CFW | `20000c64`, `20000c88`, `2000398c`, `20000c00` | `20000cac`, `20000cd0`, `200039b0`, `20000c00` |

Each third object is an external font. At observation, descriptors of both external objects were already 0; other fields including callback pointers and height were initialized. Internal objects in configuration alone do not guarantee glyph coverage or successful display. Original type-0 resolver returns if configuration pointer is nonempty; chain builder has paths skipping null items and linking fallback +`0x1c`. **There is no basis to assume a nonnull object without a descriptor is automatically excluded.** This resolver/link segment is manual disassembly analysis; the complete 173-check source audit did not verify that entire segment.

## Independent execution of callback without descriptor

`tools/verify_xip_missing_font_callback.py` copies the above native-observed objects into mock SRAM and executes the pinned original ARM callback itself in Unicorn. Only entry, arguments, and return boundary are synthetic; internal branches, code, and returns were unchanged. This is not a full main rerun or physical test.

Three images × two objects × three characters = **18 cases**. Character 0 returned false in all six cases. ASCII A and U+AC00 each produced a 16-bit read error at `0x12` relative to descriptor 0 in all twelve cases. Stock 2.4 error PC is `0x4da28e`. Result: `simulator/xip-missing-font-callback-01/report.json`.

This shows direct lookup of those characters on a descriptor-null object is unsafe. It does not establish that full main actually reaches this callback, that earlier embedded fonts cannot supply those characters, or that physical glasses experience the same error. The mock platform does not place RAM/ROM near address 0 to hide the error.

## Upstream research and remaining asset investigation

[even-g2-thai research](https://github.com/rayriffy/even-g2-thai/blob/67b5d0f1cef6031541cceccf80c57494663d1600/docs/research.md) and [2.4 rebase record](https://github.com/rayriffy/even-g2-thai/blob/67b5d0f1cef6031541cceccf80c57494663d1600/docs/rebases/2.4.0.24.md) were consulted. Commit `67b5d0f1cef6031541cceccf80c57494663d1600`, MIT LICENSE, and SHA-256/Git blob/length of three documents were verified. Preservation: `simulator/xip-font-source-research-01/sources.json`. No Thai patch or font assets were copied into Blackwall.

The author describes a separate `eOTATransmitType_FONT` channel, `s200_font.bin`, external banks, and embedded font chains. This is developer research, not verification of that channel/file's current distribution contract or assets on our glasses. Two bank addresses and 2.4 code addresses were independently compared with actual owned originals. Download location and official hash for a separate font OTA remain unconfirmed.

Next identify embedded font object descriptors/glyph coverage and actual asset supply path. In the absence of actual assets, an explicit missing-asset error diagnostic scenario is possible, but it is not substitute evidence of normal stock boot/display. Full boot, font chain completion, framebuffer, and 576×288 output remain unverified.

Follow-up bw220 separately implemented [missing-asset diagnosis](missing-font-header-diagnostic.md). Two invalid magic words confirmed original error paths and chain-builder return, not actual font load or integrated display. “No model change” above describes bw217's scope at the time.
