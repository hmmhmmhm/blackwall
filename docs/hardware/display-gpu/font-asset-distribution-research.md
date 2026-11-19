# Distinguishing official font distributions from stock XIP assets

Work bw-0219. Official distribution materials were newly examined and compared with original ARM character lookup. **Official font-metric material was obtained, but stock XIP font-bank image remains unavailable.** Existing XIP guard was not disabled for this research.

## Official distributions examined

| Material | Pinned version | Files and purpose |
| --- | --- | --- |
| [pretext](https://registry.npmjs.org/@evenrealities/pretext/0.1.4) | 0.1.4 | font_measure.js, type declarations, README, package.json; character width, kerning, CJK range information |
| [EvenHub simulator](https://registry.npmjs.org/@evenrealities/evenhub-simulator/0.9.5) | 0.9.5 | JS launcher selecting platform executable, README, package.json |
| [macOS ARM64 simulator](https://registry.npmjs.org/@evenrealities/sim-darwin-arm64/0.9.5) | 0.9.5 | 10,622,528-byte Mach-O ARM64 executable and package.json |
| [Official LVGL binding](https://github.com/even-realities/lvgl-sys-v9/tree/14b6eae3dca058153d993628cc23c152e0d8eac8) | `14b6eae3dca058153d993628cc23c152e0d8eac8` | build.rs, Cargo.toml, .gitmodules, recursive tree |

Packages were not npm-installed. Only tarballs were downloaded, checked for paths, file types, and size limits, and preserved outside Git. JS launcher, measurement functions, simulator binary, and build.rs were not executed. npm metadata SHA-1 and SHA-512 integrity were compared with SHA-256 of preserved tarballs/files. Registry-signature trust chain was not separately verified. This checks consistency with official registry distribution, not authentication of an official firmware recovery image.

Preservation: `simulator/font-distribution-research-01/sources.json`. Original registry metadata/tarballs and selected binding source/tree are in the same directory. Git blobs of three binding files were compared with pinned tree. npm/Cargo metadata declare MIT, but no separate LICENSE text was found in examined package tarballs or binding root tree. Package declaration is not expanded into permission to redistribute extracted proprietary firmware assets. Files were not copied into product code or Git.

GitHub connector rejected repository search API, so web search located the official repository; connector was used for file/tree reads. npm web pages returned 403, so official registry was read. Failure to find a verifiable current distribution URL for `s200_font.bin` in public search does not prove the file does not exist.

## Actual pretext data

Only the JSON literal following JS `const fontData =` was read with Python JSON decoder. Surrounding JavaScript was not evaluated. Material contains line_height=27 and:

- evenroster: 415 width entries and kerning data.
- evenroster_crylgrek: 299 width entries and kerning data.
- cn: default advance=320, 2,120 ranges, 2,887 exceptional widths. Not bitmap arrays or stock XIP pointers.
- evenemoji: 102 width entries.

cn ranges include U+4E2D, U+AC00, and U+D55C. Declared raw advances are 320, 294, and 294 respectively. These do not establish glyph pixels, font-bank format, or actual glasses file version.

## Differences from original ARM

`tools/inspect_font_distribution.py` verifies [bw218's native RAM copies](builtin-font-glyph-contract.md) and original mains, then calls the first chain's first two font callbacks. Only function arguments, stack, output, and return boundaries are synthetic. Original code maps RX; opcodes, internal branches, and MMIO are not replaced. Each lookup's original glyph ID is used to read raw advance from original ROM glyph descriptor and compare to official data. Kerning pairs and bitmaps are not included.

| Official data | Entries with equal width in each original image | Entries in official data absent from original callback | Width mismatches among common entries |
| --- | ---: | ---: | ---: |
| evenroster | 399 | 16 | 0 |
| evenroster_crylgrek | 299 | 0 | 0 |

Results matched across stock 2.4.0.24, stock 2.3.0.24, and Faceclaw 38. Lookups: (415+299)×3 = **2,142**. Earlier 6,036 tests check cmap contract; this is separate comparison with official material.

Missing official evenroster entries: U+0114, 0115, 011C, 011D, 0124, 0125, 012C, 012D, 0134, 0135, 0138, 0149, 014E, 014F, 015C, 015D. Whether difference comes from a specific official firmware-version change is unknown. It also does not mean official data supplies all 401 glyphs of the earlier original font. Official material is not judged byte-identical to original assets.

Final audit: `simulator/font-distribution-verification-02/report.json`, 62 file/provenance/contract checks and 2,142 original callback calls passed. First audit `-01` failed because it did not allow a newline between JSON literal and semicolon. Final tool skips whitespace after JSON decoder's returned literal endpoint before checking semicolon. Package files were unchanged.

## Boundary confirmed in official simulator

Platform package is a macOS executable, not font-bank, and contains no separate font file. Public build path in binary points to `lvgl-sys-v9/.../14b6eae/vendor/lvgl/`. This prefix matches pinned binding commit, a clue rather than proof of a fully reproducible build.

Official binding uses LVGL submodule `c033a98afddd65aaafeebea625382a94020fe4a7`. build.rs can accept `LVGL_FONTS_DIR` or `fonts` in build working directory as additional input, and public binding tree has no such font directory. The g2 feature patches missing-glyph placeholder behavior. Do not substitute this official app simulator for original ARM/chipset simulator or use it as ground truth for stock framebuffer.

## Next execution judgment

Without evidence linking actual assets to current stock version, do not supply XIP bytes for normal font load. A separately named missing-asset diagnostic scenario may be considered when investigating subsequent original main initialization. It must execute original error branches of both headers unchanged, continue blocking other XIP addresses, writes, and execution, and distinguish results from normal boot/display evidence. Do not hide [bw217](xip-font-resource-contract.md)'s null-descriptor glyph error.

Overall goals remain Faceclaw CFW for web installation, recovery boot, and stock ARM-based integrated simulator. This official-asset research is not integrated boot or screen success. Overall progress 13/29, 44.8%. No device scan, connection, RAM execution, or persistent writes.
