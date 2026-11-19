# Emulator Goal, Workflow, and Progress Review — bw352

Current progress follows the [generated dashboard](../project-dashboard.md). Figures and incomplete items below record the state at bw352.

bw-0352. At the user's request, gpt-6-astra was invoked once read-only. Rather than rerun earlier scope reviews, it examined work after the bw349 consumer contract, bw350 natural getter pass, and bw351 start of configuration writes. This does not grant authorization for later Astra execution.

## Goal and complete scope

The active Goal queried by the parent was already a G2 hardware emulator for CFW testing and matched ALIGNS and scope v3. The Goal was not marked complete or recreated. The first supported unit is one temple executing from actual ARM main reset with declared virtual phone/opposite temple/case peers. CFW feature development, web-installer productization, and physical installation/recovery certification are excluded. Full chipset cycle accuracy and original execution of both sides/case are not promised.

The complete scope is E01–04 execution foundation, E05–08 services/storage/reset, E09–12 display/input/sensors, and E13–16 peer communication/comparison/tools. Specific acceptance criteria are in [scope criteria](../data/project-scope.json) and minimal per-condition scenarios in the [roadmap](emulator-roadmap.md). Gesture types, required auxiliary sensors, peer messages, and time budgets for E11–14 were not yet pinned. Having scope by area does not mean the detailed feature list was finalized.

## Conditions for progress to rise

The old 44.8% was 13/29 in v2; recent small investigations accumulated as partial evidence for large integration criteria, so it stayed flat. Current v3 had only E01–03 complete with valid evidence: **3/16 = 18.75%, displayed 18.8%**. Full verification of one condition raises it **6.25 percentage points**; the next completed condition yields 4/16 = 25.0%. Which condition completes first depends on verification; this percentage does not estimate dates or remaining effort.

Do not raise the overall score based on task or unit-test counts. The first-screen checklist including API diagnostics, 3/6 = 50%, is not natural-boot completion either. This review added no weights, partial points, or third percentage. It presented current boundaries and next assessments together:

| Path | Verified boundary at the time | Next verification | Condition raising overall score |
| --- | --- | --- | --- |
| Natural main | Three originals read 41 GAF fields/153 bytes, then reject the first mag-bias SRAM 0774 write | Verify bw351 bias, clock variation, and GAF configuration/service as behavioral units with delay/failure controls | E05: actual app event processing after required initialization. E12: original consumption of FIFO/IRQ samples. Initialization alone completes neither |
| API display diagnostic | Original draw, completion IRQ, and nonzero guest surface; subsequent 102-word conversion unsupported | Assess display buffer → completion/wait → frame wrapper under a selected support contract. GPU reference policy undecided | M5 may be assessed first. E09 separately requires reset → natural UI → 576×288 without test caller |
| New-candidate usability | Limited to allowlist of three research images | Define candidate layout, supported device behavior, and rejection-reason contracts | E04: candidate registration, inspection, and same-runner execution. E15: complete same-scenario comparison |

## Astra recommendations and adoption

The then-current priority on the bw351 natural path was appropriate: source contracts and actual main evidence existed, while GPU sampling reference policy remained undecided. Finish the already defined bias, configuration, and service units rather than multiplying independent tools per register. Then check whether IMU initialization is required for UI activation and connect the device/transport producer. IMU completion → automatic UI startup remained an assumption.

A product risk is execution-order constraints in the current model. `BlackwallImuGafParameters.BeginRead` in `tools/renode-imu-identity.cs` restricts address order, service-completion count 2, and one getter. This limits declared initialization reproduction; it is not a general device contract supporting different ordering or rereads by new CFW. `tools/pinned_main.py` also accepts only three research images. At E04/E15, compare those support limits and **distinguish unsupported model behavior from firmware regressions**. Do not broadly weaken guards or return arbitrary ready/success now. No separate task was started merely to obtain E04 points first.

Roadmap text presenting bw346/bw348 as current was corrected to indicate progress on the natural main path while GPU selection was deferred. Dashboard next guidance was connected to current boundary, validation, and advancement conditions per path. Scope v3, 16 acceptance criteria, and completion evidence pins were unchanged. In-progress bw351 was not marked complete, and unimplemented test copies were not counted as success evidence.

## Review and verification limitations

Astra read local documentation and relevant source. The parent confirmed the active get_goal, actual getter restrictions and candidate loader, progress-tool evidence assessment of 3/16, and 14 passing progress-management regression tests. The progress tool checked hashes and specified assessment values for existing completion evidence; firmware was not rerun to revalidate it. Astra's separate Goal was null, so active-Goal confirmation relies on the parent's query. There were no new native runs, glasses access, persistent writes, external publication, or CFW feature implementation.
