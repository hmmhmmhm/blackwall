# Blackwall Agent Instructions

Read [ALIGNS.md](ALIGNS.md), the [emulator roadmap](docs/architecture/emulator-roadmap.md), and the [capability catalog](docs/architecture/emulator-capability-catalog.md) before starting relevant work. Discuss work with the user in Korean. The project is a G2 hardware emulator for testing firmware; product firmware development and physical installation are outside the active objective.

## Current status

| Scope | Result and evidence | Boundary |
| --- | --- | --- |
| Bootloader validation items 1–4 | 12 of 12 bounded virtual criteria passed; see [final acceptance](docs/bootloader/bootloader-final-acceptance.md). | Does not validate the actual Boot ROM, physical MRAM, charging case, both temples, physical recovery, or all Faceclaw combinations. |
| Original bootloader → main → screen | 8 of 8 criteria passed for the pinned stock 2.4 boot and main profile; see [completion audit](docs/bootloader/original-boot-completion-audit.md). | Starts at the original bootloader reset, not a verified physical Boot ROM. Do not substitute a patched handoff or direct main entry for this result. |
| Sustained execution after screen output | The prior 6-second and 60-second virtual execution and research scope passed 10 of 10 criteria; see [dashboard](docs/hardware/display-gpu/sustained-screen-dashboard.md). | This is bounded evidence, not a claim of complete hardware or sensor-fusion accuracy. |
| Historical scope v3 | The previous 16 of 16 functional criteria are recorded in [project scope](docs/data/project-scope.json). | This is a historical scope, not a claim that a proposed 25-criterion full-fidelity goal is approved or complete. |

Detailed historical results and the previous instructions are preserved in [agent guidance history](docs/data/agent-guidance-history.txt). Use the final acceptance above over older intermediate 11/12 reports. Do not use historical approvals to authorize a new goal, physical operation, Astra call, or external publication.

## Hardware safety

- Do not flash, trigger OTA, write persistent MRAM, replace a bootloader, overwrite vectors, or change security settings without explicit approval for that exact operation and device. An approval for one write does not authorize a later write. Never bypass protective prompts.
- Before physical installation, verify both temples' firmware and bootloader, hardware revision, case version, compatibility, recovery limits, and stock restoration path. Unknown combinations are not safe combinations. Do not promise recovery from every failure.
- Work on one temple at a time: verify startup and the recovery/restoration path before considering the other. Do not treat two-temple writes as atomic. Perform operations within a task sequentially.
- Distinguish restoration of the stock main application from full restoration of every modified persistent component. Source inspection, read-only tests, and virtual results are not physical validation.
- Keep proprietary images, device dumps, secrets, and private backups outside Git. Preserve legitimate source images, hashes, provenance, upstream commits, and verification evidence in their approved locations.

## Workflow and evidence

- Before each task, review [the dashboard](docs/project-dashboard.md), [scope](docs/data/project-scope.json), and [work log](docs/data/work-log.tsv). Use `tools/project_progress.py start` to record a task ID and `finish` to record its outcome and evidence. Reuse completed work with the same task key and input fingerprint unless a reason for repetition is recorded.
- Keep acceptance criteria, denominator, scope versions, and evidence explicit. Separate overall coverage from a smaller milestone. Do not reduce the denominator to raise the reported percentage.
- Prefer behavior-level contracts over one tool per register. Reuse pinned inputs, component hashes, and plans in `run_native_candidate.py`. Audit prior runs using their retained model, inputs, and logs; do not retroactively depend on a new candidate builder. Use schema 2 semantic contracts and distinguish `execution_passed` from `semantic_validation`. See [native candidate contracts](docs/firmware/native-candidate-semantic-contract.md).
- After verification, promptly remove reproducible build outputs, compile caches, and temporary artifacts. Record what was removed, why, and recovered space. Retain active inputs and final evidence after checking their references.
- Document research in lowercase kebab-case files under `docs/`, except the user-requested `README.md` files. Get explicit approval of final external publication drafts; a local file alone is not publication approval. Explicit user instructions take precedence over project defaults.
- Use Astra only when the user explicitly requests it for that task. Do not reuse an earlier one-time approval. Skill updates, private history collection, training-data collection, and external transfer are not automatically authorized.

## Emulator research constraints

| Topic | Required practice | Evidence |
| --- | --- | --- |
| Shared power registers | Identify the owner and phase using the actual before/proposed XOR and owner masks. Do not force guest polling or infer the owner from address or PC alone. | [Shared-domain wake](docs/hardware/communication/ring-app-wake-contract.md) |
| Observer side effects | Compare hook-on and hook-off behavior for the actual guest path. Do not assume a read-only or empty hook is behavior-free or treat a final RAM diff as a complete write history. | [Font observer](docs/hardware/display-gpu/font-wrapper-renderer-boundary.md), [M55 stack limits](docs/hardware/cpu-memory/m55-natural-stack-limits.md), [blocking wake](docs/hardware/display-gpu/nema-native-blocking-wake.md) |
| Unsupported execution | Use the verified block-begin guard; throwing `CpuAbortException` in the pinned Renode PC hook can terminate the host. Test stop boundaries with distinguishable nonzero inputs. | [Nema IRQ completion](docs/hardware/display-gpu/nema-native-irq-completion.md) |
| Pause and RTOS state | Distinguish CPU halt from a machine-wide pause; do not resume an aborted machine. Check PRIMASK, BASEPRI, IPSR, and the original caller stack; distinguish an inserted API caller from natural main execution. | [Display activation](docs/hardware/display-gpu/display-activation-native-diagnostic.md) |
| CPU context and stack selection | Validate actual pinned Renode behavior with guest MRS/MSR and exception return. The pinned build uses SP13/OtherSP22 and selection state, not nonexistent MSPCURR/PSPCURR properties; do not use host register seeding as proof of PSP selection. Observers must not write CPU registers. | [PendSV resume](docs/hardware/display-gpu/nema-native-pendsv-resume.md), `tools/verify_renode_observer_context.py` |
| Memory fixtures | Compare isolated invalid accesses with the original main memory map. Missing snapshot regions filled with zero are not proof of initialized firmware state; validate captured regions and reject missing inputs. | [ITCM contract](docs/hardware/display-gpu/glyph-itcm-read-contract.md), [blend state](docs/hardware/display-gpu/nema-blend-state-contract.md) |
| Peripheral writes | A CPU memory hook is not necessarily a veto before peripheral side effects. Validate unsupported inputs inside the peripheral before mutation. Distinguish a stop observation from proof of no side effects. | [Nema submission](docs/hardware/display-gpu/nema-submission-contract.md) |
| Executable MRAM changes | Register the affected translation block range with `OrderTranslationBlocksInvalidation(start,end)`; an empty invalidation call is insufficient. This does not model a physical instruction cache. | [Final acceptance](docs/bootloader/bootloader-final-acceptance.md) |
| Recovery boundaries | Preserve failed paths and successful alternatives separately. Do not remove the patch's power callback guard to force worker entry. | [Boot self-restore](docs/bootloader/boot-self-restore-results.md), [main-driven restore](docs/bootloader/main-driven-boot-restore-results.md) |

Use the project-installed `align` skill at `.agents/skills/align/SKILL.md` for explicit alignment requests and the focused cases described below; see [installation notes](docs/project/align-setup.md). Apply the existing agreement during routine work without starting another alignment interview.

<!-- align:begin -->
## Ongoing personal alignment

At the first relevant task in a session, check the project's required skills
against the current client's available-skill list or equivalent discovery evidence.
Check again only after a client, workspace, or installation change, or a load failure.
A file or symlink alone does not prove discovery. Load and follow **align** for
explicit alignment requests and the focused reviews below; load other required
skills when their declared task scope applies. Routine work only needs the existing
agreement, not a new alignment interview.

If a required skill is missing, distinguish discovery failure from a missing source
or runtime dependency. Report the affected skill once. A readable trusted local
source can supply the method if its needed resources are usable; disclose this as
manual loading, not native invocation. Otherwise continue independent work and
identify the blocked step. Repair only within authorized scope, preserving the
chosen installation route; do not silently add a duplicate, install globally,
or claim a required skill was used when it was not.

If user-level instructions explicitly link a personal ALIGNS.md, apply its relevant
confirmed defaults alongside this project's criteria and agreed exceptions. Keep
private content out of shared files. Do not search for unlinked profiles or promote
project feedback to global rules. Use align's personal-scope procedure when the
user requests personal setup or a consequential scope conflict remains unresolved.

Read `ALIGNS.md` at the start of work and apply its current criteria to scope,
important decisions, and result review. At an alignment session, follow its
recorded method-update policy once before loading the skill; preserve pinned
versions and use the installed method if updating is unavailable. Do not poll
for updates on every task. Use the installed **align** skill for
focused clarification when important judgment diverges, repeated corrections
suggest a missing criterion, the user is unsure of the next direction, or a loop
or goal exposes unresolved scope, completion, or stopping criteria. Compare the
request, configured objective, actual state, and results. Fix known errors directly.
Before a long run with untested boundaries, offer hypothetical rehearsal without
executing scenarios or launching the run. A review does not authorize a restart,
budget increase, or override of a user stop. The skill acts during active turns;
it cannot wake a stopped agent.

When earlier feedback could clarify criteria, offer selected PR or project
conversation review with recent/full scope and estimated time. Reuse a clear
choice; do not scan personal logs or store inferred preferences automatically.

For brief requests, use available project context and confirmed criteria first.
Ask about missing information only when it materially changes the result or
scope; group related questions. Proceed with minor reversible choices and
already delegated judgments within authorized scope. Repeated context-related
misunderstandings can warrant a focused align review of when to ask. Do not
infer a lasting preference from brevity or from a task-specific answer.

When using specialist skills, carry relevant confirmed ALIGNS.md criteria into
the task brief and result review. Keep skill defaults separate from user
preferences. Resolve conflicts already settled by the agreement without asking
again; clarify only consequential unresolved choices. Follow the applicable
instruction hierarchy and permissions, and report exceptions to specialist checks
honestly instead of rewriting criteria or claiming an unearned pass.

During an alignment session, carry each answer into the next authorized step.
Track completed, declined, deferred, and pending items in conversation context.
After completing an item, provide a next-choice step: summarize the result,
exclude completed or declined topics, recommend an eligible remaining topic,
and include a finish choice. Prefer an available structured-question tool allowed
in the active mode; otherwise use numbered text. If nothing remains, recommend
finishing without inventing gaps. Continue already requested work without another
gate, but wait before new scope. Honor stop and single-item-only requests, and do
not append alignment menus to routine work.

For Codex choice questions, an accepted request is not an answer or proof of UI
display. Do not send a final/completion response while a required async answer is
pending. Continue independent authorized work or use supported interruptible waits
of at most 60 seconds each; do not treat timeout as consent or keep waiting after
cancellation or a superseding request. Follow align's session-flow guidance for
hosts without a wait mechanism. Include “Answer questions”
only when an official resume URL is supplied or documented; never invent a link.
Resume the selected step after the answer, without another invocation request.

Account for all eight paths before choosing follow-ups. Keep unexplored paths
available; an unchosen history source or missing personal file does not exclude
paths 3 or 6. Offer path 2 conditionally if the user has a mismatch example.
Path 7 adds a README badge: offer it only after inspecting the target README and
confirming an ALIGNS.md badge is absent. Exclude existing badges and personal-only
sessions without a project; a missing or unreadable README is a prerequisite gap.
Path 8 optionally sets up personal training-data collection or export. Keep it
available without enabling collection; follow the training-data reference only
when selected or already authorized. Declining it does not limit other paths.
Path 5 is navigation. Show all remaining paths with one recommendation and a finish
choice; use numbered text if the question UI cannot fit them all. Before offering
only finish, briefly account for completed, declined, deferred, out-of-scope, or
blocked paths. Never treat a general review or rehearsal as completion of the rest.

Offer a brief return invitation only when closing a session that actually used
align to perform self-alignment. Show it at most once per session, not after each
item. For example: “Whenever you want to revisit your criteria, say ‘Let’s do a
self-alignment check.’” Adapt naturally for other languages. Omit it during
ordinary project work, installation-only work, and skill development or editing.
Reading the skill or applying existing criteria does not count as a self-alignment
session. Honor requests to omit reminders. Never load align just to add one.
Keep required next choices and pending answers intact; an invitation must not
close an unfinished session. Do not promise native routing or availability that
has not been verified.

Reuse existing answers. Fix clear execution errors directly. Ask only about
consequential uncertainty, continue independent work, and do not reopen a declined
or resolved review without new evidence. A new method version does not change
the user's agreement. Store lasting criteria only on explicit direction or
confirmation; never rewrite them to justify a mistake. Preserve `Last aligned`
unless the user confirms the whole document. Keep current criteria in ALIGNS.md
and use Git history when available. Do not initialize Git or create another log.

If align remains unavailable, apply ALIGNS.md to routine work and give the
specific discovery or installation repair needed, using the trusted source
https://github.com/hmmhmmhm/aligns.md. Do not report a method-based alignment review
as complete without loading the method. Follow the applicable instruction
hierarchy and permissions.
<!-- align:end -->
