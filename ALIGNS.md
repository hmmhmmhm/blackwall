# Blackwall Alignment

These are project criteria explicitly established by the user. Do not import personal criteria from the skill's source repository or promote a task-specific choice into a lasting preference. Respond in the user's preferred language.

## Goal and priorities

| Area | Agreed direction |
| --- | --- |
| Active goal | Build a virtual G2 hardware environment for testing stock firmware, Faceclaw, and future CFW candidates. Explore display, input, sensors, communication, storage, reset, and failure behavior. |
| First supported profile | One virtual temple starting at main reset, with explicitly declared virtual phone, opposite-temple, and case contracts. This is not a commitment to cycle-accurate full-chip or full original two-temple/case emulation. |
| Excluded from the active goal | User-facing CFW features, a web installer product, and certification of physical installation or recovery. Preserve prior research without treating it as authorization to resume those tasks. |
| Priority order | Hardware safety → recovery capability → correctness → compatibility → power efficiency → performance → new features. An iPhone app is not an initial required deliverable. |
| Initial technical sequence | Secure screen output, then complete the boot path, then improve the remaining devices and fidelity. An explicitly modeled sensor may be used without claiming real-hardware sensor accuracy. Preserve existing strict profiles. |

See the [emulator roadmap](docs/architecture/emulator-roadmap.md), [scope review](docs/architecture/emulator-scope-review.md), and [scope data](docs/data/project-scope.json). The previous product scope is preserved in [scope v2](docs/data/project-scope-v2.json).

## Completed bounded scopes

| Scope | Recorded result | Boundary |
| --- | --- | --- |
| Bootloader validation items 1–4 | 12 of 12 virtual criteria; [final acceptance](docs/bootloader/bootloader-final-acceptance.md). | No physical recovery, actual Boot ROM, both-temple/case validation, or blanket compatibility claim. |
| Original bootloader → main → display | 8 of 8 criteria for pinned stock 2.4 boot and main; [completion audit](docs/bootloader/original-boot-completion-audit.md). | The original bootloader reset and continuous path are required; a patched handoff or direct main entry alone is insufficient. |
| Post-screen sustained execution | 10 of 10 criteria for the prior 6-second/60-second virtual scope and research gaps; [dashboard](docs/hardware/display-gpu/sustained-screen-dashboard.md). | Completion does not approve or complete a full-fidelity goal. |
| Scope v3 | 16 historical acceptance criteria are tracked in [scope data](docs/data/project-scope.json). | Distinguish this coverage from current integration progress, work remaining, and estimates. |

## Operational boundaries

- Require explicit, operation-specific approval for every flash, OTA, persistent MRAM write, bootloader replacement, vector overwrite, or security change. Do not bypass protective confirmations or extend an approval to a later write.
- Check both temples, bootloader and hardware versions, and the case before physical work. Treat unknown combinations as unknown. Verify one temple's startup and restoration path before considering the other; two-temple operations are not atomic.
- Distinguish restored stock main firmware from full stock restoration of every modified persistent component. Never promise that software can recover every failure.
- Preserve original inputs, hashes, provenance, upstream commits, reproducible commands, and verification evidence. Keep proprietary images, device secrets, and private backups outside Git.
- Distinguish natural Renode M55 main execution, synthetic M55 callers, isolated M7 functions, source-only findings, unsupported behavior, and unknowns. Do not describe a collection of isolated emulations as a complete integrated emulator.
- Clean up reproducible build output, caches, and temporary artifacts after each task. Record what was removed and how much space was recovered. Preserve active inputs and required audit evidence after checking dependencies.
- Invoke Astra only on the user's explicit request for that task. A previous one-time approval or automatic review procedure is not authorization for a later call.
- For substantial design choices, explain the problem, realistic alternatives, risks, recommendation, confirmed facts, and unknowns. Continue work already authorized without reopening settled choices.
- Keep project documents under `docs/` in lowercase kebab-case, with `README.md` as the user-requested directory landing-page exception. Obtain explicit approval of a final external publication draft; follow any more specific user instruction.

## Progress tracking

- Connect each task to the active emulator scope. Track evidence-backed acceptance coverage using its actual denominator; do not turn task count or test count into project-completion percentage.
- Record a unique task ID, start, outcome, and evidence. Check prior results and input fingerprints before starting. Record why a completed identical-input task needs repeating.
- Record scope and completion-criteria changes, including their rationale and before/after definitions. Do not invent historical timestamps or results.
- Use the [project dashboard](docs/project-dashboard.md), [scope](docs/data/project-scope.json), and [work log](docs/data/work-log.tsv).

## Alignment method

- The project entry point is `AGENTS.md`. Use the project-installed `align` skill for explicit alignment requests or consequential unresolved alignment conflicts. Ordinary work uses the existing agreement without another interview.
- Trusted source: <https://github.com/hmmhmmhm/aligns.md>. The project-installed version is `align` 0.11.0; see [setup notes](docs/project/align-setup.md). Updates are manual, not automatic. Installation has been checked, but discovery in a new Codex session has not been verified.
- Do not collect private history or training data, or transfer it externally, unless explicitly authorized. Preserve `Last aligned` unless the user confirms the entire document.

Last aligned: Not yet confirmed.
