# Portable emulator progress

> This is a historical portability report. The current workflow is described in [Docker volume setup](../getting-started/emulator-report-quickstart.md).

## Verified

- The existing Renode execution uses a pinned Docker image; the host CLI and report tools accept `BLACKWALL_HOME` and use the current Python interpreter.
- On macOS, a fresh normal run with `scenarios/screen-boot.json` passed the independent audit and custom fact assertions; the final three-fact sample was also checked against that saved audit. The private report is retained outside Git.
- Report unit tests: 6 passed; custom scenario tests: 2 passed; original boot screen tests: 14 passed.
- A Linux arm64 Python container ran the scenario list, resolved the Linux data directory, and passed the custom scenario unit tests. This did not run the full emulator inside Linux.
- The temporary Python container was removed automatically and the Python image pulled for this test was removed after checking that no containers used it; Docker-reclaimed bytes were not measured. Task-generated Python cache files (106,045 bytes) were removed.

## Remaining work

The current profile still needs private frozen hardware-model components, SRAM and ITCM snapshots, exact firmware images and a pinned arm64 Docker image. A repository-only fresh setup and a full Linux or Windows emulator run have not been verified. A portable, redistributable model and reproducible multi-architecture Docker build require provenance review, implementation and end-to-end tests. The JSON scenario format currently adds assertions to one of two fixed execution paths; it is not a general-purpose script engine. The main image and the two memory snapshots currently must share a directory.

No physical hardware was accessed.
