# Managing Progress Toward the Overall Goal

This procedure maintains the complete scope, progress, and per-task records requested by the user. The current summary is the [dashboard](../project-dashboard.md), acceptance criteria are in the [scope baseline](../data/project-scope.json), and actual task history is in the [append-only log](../data/work-log.tsv).

## Meaning of progress

Scope v3 has 16 fixed acceptance criteria for a **G2 emulator for CFW testing**. The 29 mixed goals of v2 are preserved in the [original v2 scope](../data/project-scope-v2.json). The [review](../architecture/emulator-scope-review.md) explains the change and current baseline.

Each criterion has equal weight. Only `done` items with verified hashes and specified verdicts count in the numerator. Refer to the generated dashboard for the current figure. Fully meeting one criterion adds 6.25 percentage points. Partial scores, test counts, and task counts are not added. This is an **acceptance-criteria completion rate**, not an estimate of effort, remaining time, or accuracy against physical hardware.

The separate `current_outcome.gates` is a fixed checklist for current integrated behavior. It uses the same evidence/hash rules but is not included in the numerator or denominator of the 16 overall criteria. It is a verification checklist for the first display and includes API diagnostics. It is not a completion percentage for natural main boot. Refer to the dashboard for the current count. For example, increasing the number of completed stages from one to two does not change an overall 3/16 unless E09 is fully complete. Each task records newly available behavior, the previous and current execution boundaries, uncertainty removed, and the next passing condition.

Fix criteria and stages before starting. Do not split already completed small tests into criteria or remove difficult incomplete items to increase progress. If scope changes, record the version, reason, and criteria before and after. Percentages for v2 and v3 are not directly comparable. Regression or missing/changed evidence also lowers the current score.

## Starting and finishing work

Before a task, read the dashboard and recent log entries and check relevant criteria and current artifacts. Each task has a lowercase kebab-case task key reused for the same purpose and a unique ID.

```sh
python3 tools/project_progress.py report --write

python3 tools/project_progress.py start \
  --key prefetch-control-storage \
  --description 'Verify PFCR control storage and the unsupported D-cache boundary' \
  --why 'Continue existing PFCR research and incomplete tests' \
  --input tools/simulator_prefetch.py \
  --input tests/test_prefetch_storage.py \
  --scope E05

python3 tools/project_progress.py finish bw-0002 \
  --result deferred \
  --evidence docs/architecture/simulator-scope.md \
  --why 'Record the current incomplete state and next verification'
```

These commands are examples. Use the ID printed by the tool and the actual result. Completion requires `--result done` and an existing evidence file; failures and deferrals are also recorded under the same ID. Starting a deferred task with the same key resumes its existing ID instead of creating a new one.

The tool checks every past completed input fingerprint for the same key. It finds the existing A result even after A → B → A. A completed task with the same key and input fingerprint, or an in-progress task with the same key, blocks starting. Changed inputs allow a new run. Changing the input list itself to evade duplicate checking is also blocked by default. If there is a substantive reason to retest identical input, specify `--repeat-reason`. This option does not authorize hardware writes or bypass protective prompts.

The tool cannot automatically detect semantic duplicates assigned different keys. Before starting, a person must compare existing keys and evidence and reuse the historical task key.

## Records and evidence

`work-log.tsv` is a single record extending the six default show-me-your-work columns with task key, input SHA, event, scope ID, and input paths. The start row's SHA is from task start and the finish row's SHA is from task finish; the hash alone does not prove that version passed a test. Check test results and evidence for scope criteria as well. Append correction rows instead of editing history. The tool checks duplicates and appends under a short file lock and saves on exit. This prevents mistakes; it is not a security boundary against manual tampering by the file owner.

Register historical work as an `import` at the current time after checking documents, current files, and existing results. This is not a complete chronological record of every past operation. Do not invent historical execution times. A baseline input fingerprint is for duplicate lookup at registration time; it is not a reconstruction of all inputs to a past build.

Evidence may use `private:` paths. The default private root is outside Git at `~/Library/Application Support/Blackwall` and can be changed with `--private-root`. Do not put device secrets, original images, or key material in logs or scope criteria.

Update the dashboard at task start and finish; regenerate it with `report --write`. If evidence for an acceptance criterion disappears or changes, mark it `stale` and lower the completion rate. Do not automatically restart an earlier execution or perform physical work because a file is missing.

## Limits of verification and current work

A historical green result for one feature is not a green result for the entire current worktree. PFCR was initially registered as deferred during the red phase of three new tests; implementation, integration, and regression continued under the same bw-0002 until completion. Refer to the latest finish row in the dashboard and task log for current results. Even after each task ends, independently reassess its parent acceptance criterion.
