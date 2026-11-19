# Design for registering and running a new CFW candidate

bw-0355. This design implements the candidate SHA, layout, compatibility declaration, and connection to the same runner under the previously approved scope v3 E04/E15. The pinned loaders for the three original images remain in place. In keeping with the current main-reset profile, the inputs are a raw main and a JSON declaration; OTA bundle extraction remains an extension. Web installation, CFW user features, and physical writes are outside scope.

## Inputs and checks

A candidate declares a unique ID, raw-main format, cortex-m55/G2 temple target, base profile, SHA256, length, load address 0x438000, initial SP, and reset vector. Length and vectors are checked against the actual bytes. Main must fit in the current board's 0x3c0000 region; SP must be an 8-byte-aligned stack top in mapped SRAM, and reset must be a Thumb address within main. Unknown profiles and invalid sizes, vectors, hashes, or formats are rejected before execution.

The compatibility declaration is not trusted on its own. The checks verify that the base capture's main is the original pinned image and that hashes of fixed execution inputs are valid. Sixteen bytes of code at each base observer location in main are retained as anchors and compared against the candidate, including the reset entry code. This check is limited to reuse of the current observation profile; it does not certify every candidate ABI or behavior, or physical compatibility. Changed anchors are classified as an unsupported profile, and hooks at previous addresses are not silently reused.

Registration produces main.bin and manifest.json in a private directory outside Git. Both registration and execution recheck them without overwriting original inputs. The manifest cannot authorize path traversal or execution of new code.

## Connecting to the same runner

An optional firmware manifest supplies the candidate to `run_native_candidate.py`. The existing model, board, SRAM/ITCM initial values, observation, Docker execution, and semantic evaluation paths are reused; only the main bytes and memory guard based on actual length change. This length replacement requires the sole verified code anchor. No forced PC, branch, return, or TCB changes are added.

Candidate ID, hash, and base profile are recorded in the report and derived manifest separately from the existing board case. The candidate manifest is also retained in the capture. Saved audits check the preserved candidate and inputs without depending on current registry files or regeneration of the current model. The changed candidate branch is not applied to existing image runs or audits. Model-off controls and candidate replacement are not mixed; stock comparisons use separate captures.

## Alternatives and verification

Continually adding candidates to the existing SHA allowlist is not a product interface and was not chosen. Accepting OTA bundles first would expand the scope to parsers, signatures, and image selection, so it follows the initial raw-main path.

Verification consists of unit rejection tests for format, hash, size, vectors, profile, anchors, tampering, and paths, as well as preservation of existing output, runner regression, an actual run of a registered candidate with a new hash, and a saved audit. If a test fixture changes only bytes of the original that are not used during execution, it must not be presented as an independent CFW product or feature implementation. E04 completion is determined only after evidence of actual candidate connection is verified; it does not imply completion of E15 app behavior comparison or E05/E09.
