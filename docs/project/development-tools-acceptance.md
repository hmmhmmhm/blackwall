# E16 Development Tools Acceptance Audit

bw438: retain the wording and denominator of the existing 16 acceptance criteria and assess **only E16 as partial → done**. The total is 10/16 = 62.5%. Natural main (E05), normal reset initialization (E06), full UI (E09), continuous display (E10), input (E11), and sensors (E12) remain. The first-display API checklist remains at 3/6.

## Original criterion and assessment

> A developer can use one documented command to run a candidate and scenario, obtain frames/events, the reason for a stop/failure, and comparison results, and reproduce the run with a pinned profile. Verify setup in a fresh environment, guidance for missing assets, and recovery of interrupted processes as well.

| Requirement | Actual evidence | Limitation |
| --- | --- | --- |
| One documented run command | Ran the public display CLI directly without a wrapper using the [fresh environment procedure](../getting-started/fresh-simulator-workspace.md), exit 0 | Installation and restoration of private assets are prerequisites. |
| Candidate, scenario, frame/events | Stock 2.4/2.3 and Faceclaw-family RGB-zero ARM candidates; 20 display and 28 phone checks each; guest L8 binary matched PNG | Partial surface from API-insertion diagnostics, not a full UI frame. |
| Stop/failure reason | Rechecked boundary and execution/semantic reports, actual E15 regression and wrong-expectation failures, and bw437 exit 7/timeout evidence | Does not support arbitrary new firmware ABIs or every failure. |
| Comparison and pinned reproduction | All six isolated runs passed baseline comparison. Display changed by 684 bytes and phone SRAM diff was 0. Comparison JSON from direct execution also matched the isolated run. | No verification of actual MSAA or physical display accuracy. |
| Fresh environment setup | Fresh offline venv and two native libraries; restored 498 files/449,890,129 bytes with hash checks into an empty root. Six runs succeeded after blocking host reads/binds of the previous root. | Used existing Docker, LLVM, and images on the same Mac. A new OS or another device was not verified. |
| Missing-asset guidance | Actual package/private asset and missing-image guidance exited 2; missing tool and different version were simulated | No service was stopped or system tool removed. |
| Recovery of interrupted processes | Rechecked evidence hashes for actual SIGTERM/SIGKILL/timeout, owner/label verification, immutable-ID recovery, and idempotent journal in [bw437](../architecture/native-process-recovery.md). Seven journals were removed in this audit. | Recovery rejects a different host, live owner, or mismatched label. |

E16 assesses run, reporting, and reproduction tools for supported pinned profiles. A full frame from natural main without a test caller is a separate E09 criterion. Distinguish a tool-produced frame from a completed product display. The earlier E16 next action's statement that natural main/full frame is incomplete remains valid; those gaps belong to E05/E09. The completion judgment does not soften that fact or E09 acceptance.

## Evidence and preservation

- Private `simulator/fresh-simulator-workspace-research-01/acceptance-report.json`: aggregate verification of six native runs plus one direct run, module/library paths, integrity of 498 input files, guest surface → PNG, comparisons, journals, and prior E15/bw437 evidence.
- `*-command.json`, `*-guard.json`, `fresh-jobs.json`, `documented-direct-*`, `real-missing-prerequisite-results.json`, and red/green logs in the same folder: execution and failure history.
- Private `development-bootstrap-bw438-01/workspace/fresh-runs/{stock24,stock23,cfw}` and `documented-cfw-*`: actual Renode artifacts.
- Private `development-tools-acceptance-manifest.json`: seals the current code/test/doc snapshot, new inputs/outputs, installation lock, aggregate checks, and referenced evidence by size/SHA. Scope checks this manifest's SHA and required verdicts.

The first attempt failed before VM startup because the output parent was missing. After fixing it with `mkdir(parents=True)`, execution used a new output. A marker-path alias collision was fixed by rejecting it while preserving the failing regression test. The aggregator's first attempt failed because it read the bw437 manifest's string SHA format as a dict; it explicitly supports both stored formats now and completed hash verification. This aggregator error was not a guest execution failure.

Final related checks: restore 6, readiness/prerequisite 9 (included in 18 simulator pattern runs), setup 4, runtime CLI 9, display CLI 9. This does not claim that every project test was rerun. Three read-closure collections besides the seven new native runs reached preparation only and are not counted as native executions.

There was no physical device access, flashing, external publication, or subagent invocation. Next work is resolving essential dependencies of the six remaining emulator criteria, not adding a tool wrapper.
