# Project Installation of the Align Skill

Recorded: 2026-11-10. User request: “Read hmmhmmhm/aligns.md and install the relevant skill in this project.” Installation alone does not start a new alignment interview, personal-profile collection, or training-data collection.

## Actual installation

- Source: https://github.com/hmmhmmhm/aligns.md
- Reviewed commit: `43f2c30522085600883f4438ac2231ea076e87e2`
- Skill version: **0.11.0**
- Project: `<project-directory>`
- Path: `.agents/skills/align/SKILL.md`
- Installation path: project portable skills CLI supported by upstream `docs/usage.md`. Ran `npx --yes skills add hmmhmmhm/aligns.md --skill align --agent codex --yes`.
- `skills-lock.json` computedHash: `6c5cbc4b13a1f164ac71ee9ce12b749a57d8198be36d6ce31ae368767d9fd162`.
- Installed at one path only in this project. Existing user-global 0.9.1 was not modified or deleted because it may affect other projects. Blackwall instructions state that project 0.11.0 takes priority.

## Verification and connection

From the project directory, `npx --yes skills list --agent codex --json` reported align as project scope / tracked / Codex. Relative paths and SHA-256 lists of the 25 installed files were confirmed identical to reviewed upstream `skills/align/`.

After checking the conflict-free plan from official `connect_project.py --project <project-directory> --primary codex`, `--apply` was run. A managed block was connected to new `AGENTS.md` and project safety criteria were added. No symbolic links or global settings for other clients were created.

The session's starting folder was `<workspace>`. Distinguish discovery of global 0.9.1 in this session's initial catalog from project-installed 0.11.0. The new project skill was used through a **manual fallback** by directly reading it. The next Blackwall session should check native catalog and `AGENTS.md` loading. An installer listing alone does not establish that current Codex automatically loaded the project version.

## Updates

Default is manual, project-scoped `npx skills update align -p`. Updating does not change baseline files or review timestamps. No automatic updates, scheduler, hooks, periodic polling, or training-data collection were configured. If the user's instructions change, update the update policy separately.

Installation, instructions, and baseline files were local and were not committed or pushed at that time.
