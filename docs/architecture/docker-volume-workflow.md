# Docker volume workflow

## Design

`blackwall setup` validates the pinned profile, original images, memory snapshots, and model from a user-specified source against their sizes, SHA-256 hashes, and vectors before storing them in a new named Docker volume. Model files supplied by the repository retain their existing paths. Existing volumes are not overwritten. The current execution path does not use the `BLACKWALL_HOME` environment variable or a fixed private host data directory.

Each `report` execution copies the volume read-only and runs in a new output directory outside the Git repository. The output retains input copies and audit artifacts so the same capture can be re-audited; treat it as private data. The default output is in the system temporary directory and can be changed with `--output`. `doctor` revalidates the volume contents in a temporary directory.

The volume archive accepts only regular files and directories; absolute paths, parent traversal, links, and excessive sizes are rejected. A volume ownership token is checked on creation. Images must match the pinned profile, and a rejected input does not authorize physical device operations.

## Validation

- Created the `blackwall-assets` volume from existing research inputs and passed `doctor`. An attempt to create a volume with the same name was rejected without overwriting it.
- Ran a fresh stock normal scenario from the volume and passed the original boot/display report and independent audit. Audit SHA-256: `edf0252c4b30dc91900379a3e8a79dbcb06d80b160266dc608cdf0a02fb2c757`.
- Re-audited the same capture in a new output directory and confirmed the same audit hash. Removed 5,710,248 bytes of reproducible duplicate re-audit output. Original validation outputs for the normal and rejection scenarios are retained as evidence.
- The unknown boot-marker scenario passed its expected-rejection check. Audit SHA-256: `dd5e783b188beba7a4905c91aff194ee41d7c12bcc3b2e06a9b84995ee3e5a10`.
- Rejected an incorrect firmware hash, an existing volume overwrite, invalid volume names, tar path traversal, and symbolic links. Original bootloader, report, and custom scenario tests also passed.

The user must supply the stock images and private model snapshots. Results are limited to the declared virtual model and pinned inputs. No physical glasses were accessed.

After final safety hardening, the normal scenario was rerun without the environment variable and passed its audit. Audit SHA-256: `76fe577b90152a962c3f6eeabc325375d138bce2e6c723db24f91babacf746a4`. Removed 19,756,515 bytes of reproducible duplicate output; the previously retained normal and rejection execution records remain. Confirmed that inspecting a missing volume does not create an empty volume and that a preflight failure removes only the output directory created by that invocation.

Removed 11,275 bytes of reproducible Python bytecode generated for the volume module during validation. User inputs and the Docker volume are retained.

Ran a re-audit report with `--serve`, confirmed local HTTP 200, and stopped the server normally. The first selected port was already occupied, so another port was used. Removed 11,420,496 bytes of reproducible output from the two server tests.
