# Documentation reorganization

Moved 591 Markdown files from the documentation root into getting started, architecture, virtual hardware, bootloader, firmware, research, project, and previous-proposal directories. `README.md` provides a directory and overall index. In the first pass, the generated `project-dashboard.md`, execution JSON, and append-only work log stayed in place. A later pass moved the JSON and work log to [data](../data/README.md).

The [path map](../data/document-path-map.json) records old and new document/data paths. The progress tool and final bootloader audit use it to resolve historical paths. The 22 existing JSON files were not changed, and the work log remains append-only.

Validation:

- Resolved 532 distinct historical document paths in the work log to their new locations.
- Checked 1,709 local links in the docs and README. ARM instruction register notation followed by a hexadecimal address is excluded from link detection.
- The final virtual bootloader audit passed 34 checks and 12 criteria, within the existing virtual validation scope.
- A fresh virtual report execution and independent audit passed. Private results and a copy of the bootloader audit are retained as evidence.
- Passed 18 progress-management, 6 report, 2 custom-scenario, 14 bootloader-execution, 2 documentation-path, and 4 legacy package-preparation tests.

Removed temporary classification and checking files at task completion, recovering 12,782,606 bytes. No physical device was connected and no firmware was written.

## Follow-up: READMEs and data

Added a `README.md` to each documentation directory and grouped execution data and the work log under `docs/data/`. Confirmed that the SHA-256 hashes of 22 existing data JSON files matched before and after the move; old paths resolve through the mapping. After the move, the virtual bootloader audit passed 34 checks and a fresh report run was confirmed.

The 856 files in `tools/` can be found through seven topic READMEs. Their actual paths remain unchanged to preserve existing commands and pinned hashes. Scenario, web, and license directories also received guides. Removed 13,176,274 bytes of task-owned temporary research files.

Removed 12,815 bytes of temporary files used for the English agent-guidance reorganization. The source is retained in `docs/data/agent-guidance-history.txt`.

Removed 1,533,965 bytes of temporary transfer packages and scripts. Git verified the object SHA-1 hashes and package index.

Verified and packaged additional Git objects, then removed duplicate loose objects. Removed 2,268,822 bytes of temporary files used for that work.
