# Pinned research main loader and execution dependency recovery

Task bw-0113 restores execution of the original main from the three existing research inputs; it does not replace the general OTA parser or add support for new firmware. There was no glasses access, installation, or device write.

The first run failed before starting because the old audit_assets/blackwall_package source and cache could not be read from iCloud. The remote main ref exists, but tools/blackwall_package.py returned 404, so that path could not restore the source. Repository size 0 was initially taken to mean an empty repository, but that explanation was corrected after checking refs. Existing files were not overwritten and security checks were not bypassed.

The new pinned_main.py requires the same full bundle SHA for stock 2.3/2.4 and Faceclaw38 as previously allowed. It extracts main at fixed offset and length and checks the main SHA as well. All three inputs match byte for byte with the main images previously extracted and frozen by the parser, and each body occurs once in its bundle. Six altered bundles and an incorrect raw SHA were rejected. Arbitrary files, new versions, and unknown bundles are not accepted. This does not mean a new container format or CRC structure check was performed.

A later attempt also failed to read the old base fixture and stopped before Docker/guest execution. A 674-byte frozen copy of the previous unconfigured plain board was checked against hash `2c57e53eb3c5213cb20b1d2a2b6e9088aa83ddf91fa9f935dca3542b281e633c` and copied to the new renode-main-base.repl path. The original dataless fixture is preserved. This restores the CPU/M55, memory range, and strict guard placement source; it does not manipulate guest code or PC.

The host-source directory in each new main run retains copies of the runner, pinned loader, pin source, and Docker execution helper. These are audit snapshots, not a completed standalone replay package. The original main entry, synthetic board responses, absence of physical timing, and incomplete full boot remain limitations.

Evidence: private pinned-main-loader-01/source-report.json, validation.json, and fixture-recovery.json. Pre-execution failures remain in launcher.log under multi-uart-main-stock24-01/02.
