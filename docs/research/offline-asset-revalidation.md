# Hash revalidation of retained research assets

Task bw-0111. This refreshes existing R1/F1 evidence without changing completion criteria or their denominator.

The existing `docs/data/offline-asset-audit.json` (3,082 bytes) was in an iCloud compressed/dataless state and reads failed with `TimeoutError60`. The aggregation tool excluded R1/F1, which referenced this shared evidence, as stale and displayed 11/29 rather than 13/29. Reads continued to fail after a targeted download request. Do not change or rewrite the original file or old SHA. Reusing the cached older audit function also failed because its source/pyc could not be read. This failure is not recorded as a successful asset check.

A new independent verifier checked current SHA-256 and sizes of four files retained outside Git: stock 2.3/2.4, an existing boot-target bundle, and Faceclaw38. They also matched the existing private research/offline-check manifest. This establishes identical bytes associated with the earlier version/provenance record; it does not mean they were newly downloaded from an official server or that provenance was revalidated. No new build, format/CRC reparse, bootloader structure check, or recovery test was performed. Physical installation readiness remains false.

The new report is private `simulator/offline-asset-revalidation-02/report.json`; the verifier copy and hash are retained in the same private directory. Incorrect expected pins and missing assets were rejected. R1 directly pins the new report, verifier, and four actual asset hashes; F1 retains the report, verifier, and existing direct CFW pin. Original evidence and documents remain in `project-scope.json` under `evidence_updates`. This revalidation does not replace R2/R3 boot or recovery validation.

An independent source/manifest/report review used the same GPT-6 family. This refresh does not weaken the existing asset-identity condition and does not mean access to the historical JSON was restored.
