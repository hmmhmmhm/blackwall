# Raw Main Candidate Registration and Verification with the Same Runner

bw-0356. Instead of adding hashes to the allowlist of three existing research images, this implements a path to **register a new candidate with separate ID, SHA, length, vector, and compatibility declaration and run it in the same Renode runner**. Only raw main is supported; this is not OTA installation, signature authentication, or physical compatibility verification. It implements the input path in the [design](firmware-candidate-registration-design.md) and scope v3 E04.

## Registration contract

`tools/firmware_candidate.py register` takes raw main, a JSON declaration, a base capture, and a private output folder. Declaration fields are schema1, id, format=raw-main, target=g2-temple-main, cpu=cortex-m55, profile, load_address, main_bytes, main_sha256, initial_sp, and reset_vector. Profile is one of the currently supported stock_current/stock_base/cfw families.

Length, hash, SP, and reset vector are compared with the actual file; load address 0x438000, main region 0x3c0000, aligned SRAM stack top, and Thumb reset within main are checked. It also checks that base capture main is the family's pinned original and saved execution-input hashes are valid. Main observer points and a 16-byte code anchor at base reset entry are compared with the candidate. The existing pinned loader was unchanged.

Registered main.bin and manifest.json are rechecked at execution. Other profiles, changed anchors, tampering, path traversal, and overwriting existing outputs are rejected. Anchor agreement is a **limited check for reuse of the current observation profile**, not certification of all firmware ABI or functional compatibility. If a new build changes an anchor, treat the profile as unsupported and re-review observation points.

```sh
python3 tools/firmware_candidate.py register \
  <raw-main.bin> <declaration.json> <base-capture> <new-private-registration-folder>

python3 tools/firmware_candidate.py check \
  <registration-folder/manifest.json> <base-capture> --profile stock_current

python3 tools/run_native_candidate.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <reviewed-plan.json> <new-private-capture> --case stock24 \
  --firmware-manifest <registration-folder/manifest.json>
```

Base capture and plan source/board families must match. The manifest does not execute Python, commands, or arbitrary paths. Existing models, board, SRAM/ITCM, observations, and Docker isolation are reused; only candidate main and the memory guard based on its actual length are substituted. No additional PC, branch, return, or TCB changes occur. Report board case and `firmware_candidate.id` are separate, and candidate hash/length and registration snapshot hash are recorded.

## Actual verification

A candidate appending a 16-byte test marker to the end of stock 2.4 raw main was used. It is neither a user feature changing original code nor an independent CFW product. Length changed 3700068→3700084 bytes and candidate hash differs from all three existing research images. This fixture tests actual use of the new main length, hash, and registration path.

- After registration, the same runner executed from main reset to the existing first GAF service-request boundary. It read the appended 16 bytes of actual guest main and confirmed fixture agreement.
- An original-image control was also run. CPU and all observations of both runs exactly match the existing baseline; board, strict model, initial SRAM/ITCM, and probe are identical. The only run.py difference is memory-guard main length. Marker observation common to both paths is post-stop diagnostics.
- Nine unit tests for invalid declarations, vectors, hashes, format/target/profile, anchors, paths, and failed length substitution passed, as did 13 existing runner semantic-contract tests. Six tampering types in actual registered copies were rejected and existing registration folders preserved.
- Two saved audits for candidate and original passed. They were checked while the registry was temporarily unavailable, confirming no dependence on the current registry, then it was restored. Audits use capture candidate manifest/main and pinned inputs.

E04 demonstrates registration, checking, and execution connection for a new candidate. This fixture's same boot boundary is not promoted to completion of regression comparison for new app features (E15), normal app startup (E05), or natural UI (E09). Unsupported instructions/MMIO or semantic contract failures remain candidate execution results; successful registration does not mean firmware operates normally.

## Preservation and re-audit

All binaries, captures, and declarations are outside Git in `~/Library/Application Support/Blackwall/simulator/firmware-candidate-registration-02/`, together with source and inspector snapshots.

- `registered/`: new candidate raw main and registration manifest.
- `candidate/`, `legacy-control/`: two actual runs.
- `candidate-audit/`, `legacy-control-audit/`: two audits without native rerun.
- `baseline/`: private copy of pinned original execution inputs needed for checking.
- `preflight.json`, `audit-isolation.json`, `verification-report.json`: rejection and registry-independence records/checks.
- `evidence-manifest.json`: evidence/source file hashes and E04 verdict.

Ordinary saved audit uses `run_native_candidate.py --audit-existing --audit-output <new-audit-folder>`; the firmware-manifest option is not resupplied. This fixture's integrated evidence check is:

```sh
python3 tools/verify_firmware_candidate_capture.py \
  "$HOME/Library/Application Support/Blackwall/simulator/firmware-candidate-registration-02" \
  <new-verification-json>
```

Preparation failure from incorrectly expecting an initial 17-byte marker to be 16 bytes and a failure where the inspector's flat-file hash function rejected nested exports were preserved. Nested-export checking was corrected to inspect paths/hashes inside capture directly; native runs and original evidence were unchanged. No physical access, flash, OTA, permanent writes, or external publication occurred.
