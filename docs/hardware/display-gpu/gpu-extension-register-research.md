# Official Nema register definitions and initialization boundary

Status: official-source research and diagnostic catalog verification complete. GPU execution model and actual main's last boundary remain previous 0x40090388 write 1. Full boot, integrated screen, and physical verification remain incomplete.

## Newly confirmed sources

Official Ambiq Zephyr pinned commit `89c8a36fb2af42b8ce83a30ea8b5dcada9442ccc` west.yml points to public HAL AmbiqMicro/ambiqhal_ambiq `d3278ec49a534728384537557dd44b205ec72129`. That HAL's components/graphics/NemaGFX_SDK/headers contains internal register headers. Commit objects and trees were verified separately; SHA256/Git blobs of ten source files were checked. Full SDK/binaries were not installed and libraries were not run.

Commits, paths, and hashes are in [source snapshot](../../data/gpu-extension-upstream-snapshot.json). Official SDK headers include Think Silicon permission. API version is 1.4.12 and blob matches existing LVGL source nema_cmdlist.h. This does not prove G2 firmware SDK version or full ABI identity. Existing power model was not replaced by new HAL.

## Register names confirmed

| Offset | Official SDK name | Current judgment |
| --- | --- | --- |
| 0x388 | NEMA_RAST_BYPASS | Name/address confirmed; individual bit meanings, detailed value-1 behavior, reset effect undetermined |
| 0x148 | NEMA_CLID | SDK definition supports earlier CLID inference; physical behavior unverified |
| 0xe8 | NEMA_CMDSTATUS | Command-processor status/control boundary; full actual reset effects unimplemented |
| 0xec | NEMA_CMDRINGSTOP | Boundary used in initialization/submission; not treated as side-effect-free storage |
| 0xf0 / 0xf4 | NEMA_CMDADDR / NEMA_CMDSIZE | Address/size names; consistent with byte-footer observation in current three runs |
| 0xfc | NEMA_STATUS | Official Zephyr driver reads for GPU busy; distinct from public metadata write-reset description |
| 0x1f0 / 0x1f4 | NEMA_CONFIG / NEMA_CONFIGH | SDK capability names; actual values/support require separate confirmation |

STATUS name at 0xfc does not negate write-reset semantics or establish every read/write side effect. Source-specific names and read/write paths remain distinct. Earlier judgment not to treat metadata's 0x148 DRAWPT2Z label as established actual coordinate meaning remains.

Pinned library init_nema_regs and three firmware images write 1 to 0x388, but name alone does not establish rasterizer disabled/enabled or side-effect-free storage. GPU model was not changed here to allow the write. Ring preservation/revalidation after reset remains undetermined.

## Diagnostic catalog

[SDK register map](../../data/gpu-sdk-register-map.json) is derived material separating 106 literal register names (104 unique byte offsets) and command constant NEMA_HOLDCMD. The constant is 0xff000000; observed initial footer 0xff0000f0/0xff0000f4 arithmetically matches HOLDCMD OR CMDADDR/CMDSIZE. This alone does not implement opcode execution/wait/jump semantics or GPU completion.

`tools/build_gpu_register_catalog.py` checks pinned header SHA and looks up names. It is material for naming unsupported addresses, not a write allowlist, read values, reset policy, or decoder. 106 register literals and one command constant were checked against header with ARM C static assertions. First attempt classified HOLDCMD as an offset and was rejected by range check; it was separated as a command constant. Three cases confirmed modified source/out-of-range addresses rejected and existing outputs not overwritten.

```sh
python tools/build_gpu_register_catalog.py <pinned-nema-regs.h> <new-output.json> \
  --address 0x40090388
```

Think Silicon copyright, permission, and normative-header notices are preserved in [license](../../../licenses/think-silicon-nema-headers.txt). Original headers/additional drivers remain outside Git; firmware/private backups are not included.

## Limits of official driver reference

Pinned Zephyr driver checks busy on suspend with NEMA_STATUS and uses CMDSIZE as byte size for cache flush. Code itself describes this path as heuristic, so it does not verify G2 cache ordering, physical stability, or ring reset retention. That driver was not adopted or run in Blackwall.

## Next work

Compare register catalog to actual command-generation functions to narrow initialization role of 0x388 value 1, connecting only a model with confirmed behavior. Then separate post-reset binding from submission/command execution. Do not store unknown registers wholesale or assume command completion.

Private gpu-extension-research-01 preserves source-manifest.json, provenance.json, register-catalog.json, catalog-assertions.c/o, catalog-compiler.log, and catalog-verification.json. Previous execution-model source hash was confirmed unchanged; no new main/physical run.

Official sources: [HAL header](https://github.com/AmbiqMicro/ambiqhal_ambiq/blob/d3278ec49a534728384537557dd44b205ec72129/components/graphics/NemaGFX_SDK/headers/NemaGFX/Nema/nema_regs.h), [Zephyr manifest](https://github.com/AmbiqMicro/ambiqzephyr/blob/89c8a36fb2af42b8ce83a30ea8b5dcada9442ccc/west.yml), [GPU driver](https://github.com/AmbiqMicro/ambiqzephyr/blob/89c8a36fb2af42b8ce83a30ea8b5dcada9442ccc/drivers/gpu/gpu_ambiq.c).

Count correction: prior “106 offsets” meant number of names. Two aliases, CONFIG/LOADCTRL (0x1f0) and C3/CMAX (0x20c), make 104 unique offsets. Current catalog separately reports names, unique offsets, and aliases. Original private catalog and 107 macro assertions were preserved.
