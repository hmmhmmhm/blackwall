# Original ARM draw-command list writing

bw-0248 executed the path after binding function in [target-buffer contract](ambiq-target-buffer-contract.md). Original code was confirmed to write actual command words to RAM. GPU execution, rasterization, framebuffer, panel output, and full main boot remain incomplete.

## Original path executed

| Role | Stock 2.4 | Stock 2.3 / Faceclaw 38 |
| --- | --- | --- |
| Texture binding | 0x4d2edc | 0x4c552c |
| Circular-list bind candidate | 0x5612f0 | 0x5303dc |
| List unbind candidate | 0x5613d6 | 0x5304c2 |
| Reserve word space | 0x561a08 | 0x530af4 |
| List rewind candidate | 0x5612a0 | 0x53038c |
| Nema state global slot | 0x20077b40 | 0x20078314 |

`tools/inspect_ambiq_commands.py` verifies pinned bundle SHAs and original function signatures/calls. It maps original main RX in Unicorn and executes each function from original entry through return. No branch/function-return/opcode substitutions or observer hooks. GPU/MMIO areas are not mapped.

Synthetic inputs are state pointer at global slot, zero initial state, preallocated 512-byte list and descriptor, texture data/arguments, and stack. Descriptor byte size, pointer, and word capacity are test conditions matching original consumer code. No objects created by original allocator or full main were obtained. Original bind itself sets active list pointer. This is a standalone binding-function test, not forcing the previous target function past locking.

Original bind connected current list under two sector conditions and set sector size, ID, and flags. Binding added six words through original reserve function. A second binding after the first preserved existing six words and advanced offset 6→12. Unbind wrote `[0x50000, 0]` at offset 12 and disconnected current list. Rewind returned offset to 0 while preserving existing command bytes.

## Commands written and error conditions

For test index `i`, data pointer `p`, dimensions `w/h`, format `f`, stride `s`, actual six words were:

```text
[i*16, p, i*16+4, (f<<24)|s, i*16+8, (h<<16)|w]
```

Tested index 0, 64×32/format 9/stride 128 and 256; index 1, 11×16/format 8/stride 16. Second binding in each condition increased stride by 16. These are synthetic inputs. Part of original GPU command-list format was confirmed; words were not applied to actual GPU registers or their meanings verified with a decoder.

- Three images × three conditions × two bindings = **18 command writes**. Results matched across images.
- Without a list, original error word received `0x80` and list data stayed unchanged. Binding's own state cache can update before error, so full state rollback is not claimed.
- Circular bind with physical pointer misaligned by one byte recorded original error `0x4000` and did not activate list. Two error conditions × three images = **six cases**.
- Bind, binding, unbind, rewind, and errors total **51 original function calls**. PC/SP and callee-saved register returns checked for each.
- Final memory comparison showed synthetic SRAM unchanged and work-area changes confined to allowed state object, descriptor, list, and stack ranges. Texture pixels unchanged. This does not evidence every transient write history.

Insufficient list capacity, implicit submission at sector boundary, expanding allocator, GPU completion/IRQ, actual cache coherency, and OS locking were not included. Results using sufficient list capacity are not expanded to safety of small lists.

## Evidence and next steps

Final result outside Git: `simulator/ambiq-command-list-02/report.json`, preserving input raw SHAs, function addresses, words/state results, and pinned execution/dependency copies/SHAs. `-01` was earlier first-binding-only result; `-02` added append boundary. Separate `simulator/ambiq-command-verification-02/audit.py` passed 80 checks comparing pinned originals/tool hashes, function entry bytes, expected words/append/terminator/rewind/errors, and three-image correspondence. Python compile passed.

Next connect original glyph helper bitmap, transformation matrix, and draw-command-writing path to this list. Actual submission remains a separate boundary; do not add arbitrary GPU completion response or successful handling of unsupported commands. Overall fulfillment remains 13/29=44.8%, scope v2. Actual device, web installation, and persistent storage unchanged.
