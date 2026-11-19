# First Simulator Runner Plan

This is the first unit of the development sequence approved by the user. At that time, the full simulator, display, and web-installation objectives remained in scope.

**Purpose:** Starting from actual main reset, report the first unimplemented access or execution limit reproducibly.

**Structure:** `tools/firmware_runner.py` handles input hashes, extraction, CPU execution, and stop reporting. It does not import network or device modules. Actual images start in isolated main-reset mode. Existing boot-handoff integration is a separate subsequent unit.

**Environment:** Unicorn 2.1.4 in the preserved Python environment, Python standard library, and existing bundle parser.

## Work and verification

- [x] `tests/test_firmware_runner.py`: use synthetic Thumb code to check unmapped read/write/execute, code-region write protection, and loop instruction budget. Reaching a time limit is not treated as success.
- [x] `tools/firmware_runner.py`: check stock 2.3/2.4/Faceclaw input SHA and map main raw read/execute only. Initialize SRAM to declared values. Leave MMIO/ROM unimplemented; do not automatically map them.
- [x] On unmapped access, record PC, address, size, access type, and recent execution addresses and stop. Record PC, SP, initial vector, Unicorn version, CPU model, and assumptions in JSON. Save reports only as new files.
- [x] After synthetic tests pass, apply the same instruction limit to three actual images. Run each image twice and compare stop reason/location and execution-address records. Save results in private paths.
- [x] Record results and unimplemented models in `docs/architecture/simulator-runner-status.md`. Do not describe an unmapped access in main-reset mode as a physical-device boot failure.

Verification command:

```sh
/tmp/blackwall-research-GJjXQFhx/offline-venv/bin/python -m unittest discover -s tests -p test_firmware_runner.py -v
```

The individual-run interface is `firmware_runner.py IMAGE --output REPORT --instructions 10000`. IMAGE is a pinned official/Faceclaw full bundle and REPORT is a private path that does not exist. Output indicates actual termination reasons such as `unsupported-memory-access`, `unsupported-execution`, `instruction-limit`, or `time-limit`, not a pass. No option connects to a physical device or writes firmware.
