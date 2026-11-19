# Project data

This directory contains configuration, progress state, and work records referenced by the emulator and research validation tools. Start with the [documentation index](../README.md).

| File | Purpose |
| --- | --- |
| `agent-guidance-history.txt` | Original AGENTS and ALIGNS text preserved before the English reorganization |
| `document-path-map.json` | Mapping from previous document and data paths to their current locations |
| `work-log.tsv` | Append-only record of task IDs, inputs, results, and evidence |
| `project-scope.json`, `project-scope-v1.json`, `project-scope-v2.json` | Current and previous acceptance criteria and evidence |
| `emulator-fidelity-scope-proposal.json` | Proposed emulator fidelity objectives |
| `original-boot-stock24-profile.json` | Inputs and model hashes for virtual stock 2.4 boot |
| `original-boot-screen-progress.json`, `sustained-screen-progress.json` | Progress records for screen output and sustained execution |
| `bootloader-validation-progress.json`, `bootloader-validation-matrix.json` | Virtual bootloader validation criteria and version combinations |
| `bootloader-additional-profile-evidence.json`, `bootloader-binding-candidates.json` | Additional profile evidence and bootloader candidates |
| `recovery-artifact-profiles.json` | Artifact profiles for virtual recovery analysis |
| `gpio-register-map.json`, `gpio-output-register-map.json`, `gpio-interrupt-register-map.json` | GPIO register research |
| `gpu-sdk-register-map.json` | GPU SDK register research |
| `gpu-upstream-snapshot.json`, `gpu-extension-upstream-snapshot.json` | GPU-related upstream snapshots |
| `imu-gaf-default-profile.json` | Default virtual IMU and GAF profile |
| `offline-asset-audit.json` | Offline asset validation record |
| `faceclaw-main-anchor-candidates.json` | Candidates for Faceclaw main execution-path analysis |
| `upstream-snapshot.json` | Upstream project version record |

Historical data retains the paths used at the time to preserve its contents and hashes. Supported tools use the path map to find current locations. Stock firmware images and private backups are not included in this directory.
