# Creating a Local Preparation Package

`tools/prepare_package.py` creates three individual components and a web-screen snapshot from a verified CFW bundle, stock 2.4 bundle, and dedicated-key boot component. It does not import or run device transport. Before extraction it checks source bundle SHA, component CRC, and main bounds. The boot component requires the exact candidate SHA.

Output must be a new directory outside Git. Existing output and output inside the repository through symlinks are rejected. Directories use mode 0700 and generated files 0600. After rereading all files and checking their SHA values, it writes manifest.json last. A failed intermediate directory is retained for investigation and considered incomplete if it lacks a manifest.

Actual generated and verified location:
`~/Library/Application Support/Blackwall/packages/preparation-01/`

- components/main-cfw.bin
- components/main-stock.bin
- components/boot.bin
- web/ screen and modules
- docs/ recovery manual and candidate records
- NOTICE.md, licenses/, manifest.json

The lengths and SHA values of 15 output files were checked both by the generator and independently. The component files' 0600 mode and absence of firmware in web/ were also checked. Fifteen Python tests passed, including existing validators.

Reproduction command (specify a new output directory):

```sh
python3 tools/prepare_package.py \
  --cfw '/private/recovery/faceclaw-38-research-only.bin' \
  --stock '/private/recovery/stock-2.4.0.24.bin' \
  --boot-component '/private/recovery/boot-recovery-component.bin' \
  --output '/private/packages/new-preparation'
```

The input paths above are examples. The actual inputs at the time were under recovery/private-boot-candidate-01. A web server must serve **only web/**, not the package root. Do not serve paths containing images or recovery keys over HTTP or publish them externally.

This package is a review artifact for installation preparation. Keep `installable=false` in the manifest. Recovery keys and the independent host are retained in a separate recovery directory; this bundle alone cannot perform recovery. Device inventory, mixed boot/main/codec compatibility, actual recovery, and full-stock restoration remain unverified. The UI is still inspection-only. A file list or hashes do not mean the overall objective is complete.

The later preparation-02 is a new snapshot containing the planning UI and coordination modules. Eighteen generated files were confirmed by independent hash checks. preparation-01 was retained. Both packages remain `installable=false`.

## 2.4 recovery candidate package

The 2.4.0.24 research candidate was separately packaged at `~/Library/Application Support/Blackwall/recovery/packages/preparation-03/`. Existing preparation-01/02 were retained. This package includes `components/boot-24.bin`, two main components, the web inspection screen, and case, dump, checksum, and recover binaries with their respective metadata in `recovery-kit/`. Lengths and SHA values of 29 files were independently compared with the manifest.

The generator's `--recovery-candidate` option compares the candidate boot, patch, recovery tools, and key-identification hashes against a pinned profile. Boot component payload and raw boot must match; tool metadata lengths, hashes, link bases, and RAM entries are checked too. Mixing recovery tools from 2.3 and 2.4 candidates is rejected. Key files are not copied. The key and independent host environment are needed in the original private recovery path. The boot binary itself is also a private artifact, so do not publish the complete package externally.

```sh
python3 tools/prepare_package.py \
  --cfw '/private/recovery/faceclaw-38-research-only.bin' \
  --stock '/private/recovery/stock-2.4.0.24.bin' \
  --boot-component '/private/recovery/boot-2.4-research-component.bin' \
  --recovery-candidate '/private/recovery/private-boot-24-candidate-01' \
  --output '/private/packages/new-2-4-preparation'
```

The paths are examples for reproduction. `bootOperation=boot-24` in the manifest identifies the candidate; it does not declare transport support. The web screen can inspect and plan for this candidate only. The preparation-03 snapshot's OTA session does not support the 2.4 candidate. A later session module adds mock-verified 2.4 candidate handling, but the installation gate remains. Keep `installable=false` and `hardwareValidation=none`. The case fixture 1.2.57 is not a confirmed version of the user's case. Combined Faceclaw/codec compatibility, physical boot and recovery on both sides, and full-stock restoration remain unverified.

The package docs are a snapshot from generation time. Consult the working repository documentation for later clarifications. Four package-generator unit tests and 41 web tests including actual private inputs passed.

## 2.4 session supplement snapshot

The later `recovery/packages/preparation-04/` includes boot-24 session handling and transport validation documentation. The generator retains the same 2.4 boot/recovery-tool profile checks. Session handling is mock-verified only, and installation through the actual web screen remains blocked. `installable=false` and `hardwareValidation=none` are unchanged. Do not overwrite preparation-03 or earlier bundles.
