# Nema execution tools and shader reuse research

Follow-up bw256 correction: 50/42/42 differences below were actual fixture results at that time but affected by missing 2.4 Nema global SRAM. After collecting/restoring state from original main, all three inputs followed the 42-word ROP path. Do not interpret as version-specific shader difference. Use [correction and reproduction](nema-blend-state-contract.md) as current reference.

bw-0255. Three saved original ARM command lists were compared with public register headers. No GPU execution or pixel generation. Research prevents mistaking a public CPU library for a GPU executor.

## Reusable materials

- Nema library path in LVGL `cff1c632206a267534102ee1065f51ac87be4099` contains ARM archives for Cortex-M33/M55/M7. Existing archive disassembly is comparison material for command generation and ring submission; it does not by itself provide a GPU raster simulator.
- Full 2,117-entry tree of Ambiq `ambiqhal_ambiq` `d3278ec49a534728384537557dd44b205ec72129` was additionally obtained, response truncated=false. Shader-related paths are public API headers; this path search found no executable GPU emulator or shader ISA implementation. It does not prove absence from all file contents.
- Existing LVGL tree 6,928 entries and Ambiq port tree 289 also have truncated=false. Simulator/emulator path searches found no reusable Nema command executor. Search alone does not establish that commercial/private tools do not exist.
- Header describes `nema_load_frag_shader` as uploading precompiled shader to internal GPU memory, and `nema_set_frag_ptr` as specifying internal fragment-shader location. There is no basis to interpret these as CPU addresses or ARM opcodes.

Think Silicon copyright/permission notices and hashes of headers are preserved in existing [upstream manifest](../../data/gpu-extension-upstream-snapshot.json). No external library was newly copied, linked, or adopted as a dependency.

## Differences observed in actual commands

`tools/inspect_nema_batch_profile.py` checks saved M55 report success, final WORK hash, and actual RAM command words against baseline snapshots. It also checks pinned register and blender header hashes. It does not execute GPU commands.

| Input | Payload words | Observed blend/shader settings |
| --- | ---: | --- |
| Stock 2.4 | 50 | IMEM_ADDR=0, four DATAH/DATAL words, CODEPTR=`0x141e8000` |
| Stock 2.3 | 42 | ROP mode=`0x504`, CODEPTR=`0x141f801f` |
| Faceclaw 38 | 42 | Same ROP mode/CODEPTR as stock 2.3 |

2.4 upload words in order are `080c0003`, `0a012007`, `004e0002`, `804b1286`. Public header names `0xc4/0xc8/0xcc` IMEM_ADDR/DATAH/DATAL. Names and observed transfer order were confirmed; internal address increment, instruction boundaries, and meaning of each opcode were not.

Public blender header has SRCALPHA=4, INVSRCALPHA=5. **`0x504` combines two NEMA_BL_SIMPLE factors; NEMA_BL_SRC_OVER is `0x501`.** Calling the observed older value simply SRC_OVER would be wrong. Header alpha formulas alone do not establish actual channel conversion/integer rounding for A4 source and L8 destination. Whether 2.4 shader and older ROP yield identical final pixels was also unknown.

## Additional documentation availability

[Official Ambiq Apollo510 content portal](https://contentportal.ambiq.com/ca/apollo510?delta=40&start=2) lists Nema Pico GPU Users Manual v1.0, document ID `A-SOCAPG-UMGA06EN`. Actual download request redirected to **Submit Profile HTML** rather than PDF. Do not report reading the PDF or verifying G2-generation compatibility. No profile submitted or account created. Response, redirect URL, and hash are preserved privately.

[EU CORDIS GPU-WEAR results](https://cordis.europa.eu/project/id/717850/results) list titles for Think Silicon Shader-Edit documentation and Vertex Processor ISA. Only the list was checked; contents were not obtained. In particular vertex ISA cannot be assumed to be the current fragment ISA.

## Judgment for next execution

Reuse obtained CPU archives and headers to trace original blend-setter arguments, branches, and shader-upload generation. Next establish in original code which public API operations correspond to the two firmware families' configurations. Do not invent pixels or inject completion IRQ because documentation is blocked.

Subsequent choices are vendor runner reuse, full fragment ISA implementation, or a functional model supporting only verified operations. None was selected at this point. Even with a functional model, distinguish original CPU execution, GPU functional approximation, and unverified timing; stop on unsupported shaders. Obtain evidence of operation semantics before discussing implementation scope. Font preview does not replace integrated framebuffer success.

Original main SPI boundary, normal external font-bank acquisition, and web installation/recovery integration remain. Overall completion **13/29=44.8%, scope v2**. No physical access or firmware writes.

## Evidence

Outside Git in `simulator/nema-execution-reuse-research-01/`:

- `ambiqhal-tree.json`, `tree-provenance.json`: pinned commit full tree, hash, search paths.
- `apollo510-portal.html`, `portal-provenance.json`: actual official portal response.
- `manual-download-response.html`, `manual-provenance.json`: evidence PDF was not obtained and redirect to profile page.
- `batch-profiles.json`: RAM/hash/word comparison and register trace of three original M55 batches.

Initial analyzer rejected input WORK by comparing it to final WORK hash. It was corrected to use saved runner `result/final-work.bin`; rerun analyzed saved data only. Native firmware was not rerun. This failure is not interpreted as a GPU or firmware problem.
