# Next Simulator Behavior Units and Display Prerequisites

> 2026-11-13 bw342: Active scope is emulator-only scope v3. For current status and reproduction, prioritize the [capability catalog](emulator-capability-catalog.md); for the next sequence, use the [emulator roadmap](emulator-roadmap.md). Below is an earlier-phase record; do not treat historical progress, priorities, or initial CPU tables as current state.

## Priority at bw340

The [display queue-36 contract](../hardware/display-gpu/display-queue-producer-contract.md) executed all kind-3 producers and original queue send/receive for three originals, confirming messages 0 → 1 → 0, receiver 1 → 0, and exact 36-byte copy. The consumer is an isolated test stubbing three preparation helpers and one eligibility helper; snapshot mode is currently 0. In a diagnostic supplying mode 1 and eligibility, six arguments reach the driver wrapper → actual ROM callback entry, but callback body and pixels do not execute.

Next are the **actual producer of the kind-1 activation message, preparation helpers, and a legitimate UI initialization path**. Do not judge isolated tests changing mode or injecting queue messages as natural main/display success. Do not arbitrarily extend unknown ROM defaults for the IMU getter's 41 fields/153 bytes to zero. Retain current task/wait judgments from the [bw339 sensor/UI audit](../hardware/sensors-input/imu-startup-ui-dependency-audit.md).

Recorded ARM 72/frozen 72, nine mutation negatives, 11 unchanged models, and zero new native runs. Overall 13/29 = 44.8%, scope v2, and physical-device approval boundaries remain. Below records earlier reviews and progress; the execution order at that time prioritized this section.

The one-off Astra review requested by the user for bw-0238 was adopted. All 29 conditions, scope v2, 44.8%, and hardware-approval boundaries remained. Earlier phase results are preserved in individual evidence documents and the append-only work log.

## Endpoint confirmed at the time

Execution advanced through UART0 transmit/IRQ → TIMER7 → touch/GPIO → IOM6 power, initial configuration, retention storage, and power-off. [bw242 follow-up](../hardware/power/iom6-retention-copy-contract.md) stops in three originals at GPIO117 reset/ready assessment. The limited-mode-off control exactly matches the prior CQFLAGS boundary. Global CQ inputs and actual GPIO are unknown; first SPI transmission, normal font bank, full boot, and integrated display remain incomplete.

## Next work order and stop criteria

| Order / area | Next unit available for review | Pass / stop criteria |
| --- | --- | --- |
| Complete · D5 shared verification bw239 | Schema 2 expectations, saved re-audits, host mutation verification | Unit 11/host 52 passed. Historical reports unchanged. Complete integrated developer tool D5 remains incomplete |
| Prerequisite complete · D3 bw240 | Confirm original bitmap conversion and caller-buffer writes for representative glyphs | 96 callbacks/863 checks. Generic lifetime, natural UI, and framebuffer still incomplete |
| First integration complete · W5 bw241 | Browser UI → OTA → RAM; stored image → limited ARM handoff | Web 62/ARM 16, two corruption rejections. Full boot, failed transport, recovery manager, and browser-to-ARM integration incomplete |
| In progress · S6 bw242 | After IOM6 retention-copy verification, EM9305 reset/ready, GPIO117, and first peer contract | Initialization/first transfer incomplete. Do not fabricate unknown external flags or peer responses |

[Shared semantic verification](../firmware/native-candidate-semantic-contract.md) was implemented. New schema 2 plan `passed` is true only if both execution and semantic verification pass. Existing schema 1 is distinguished as `legacy-capture-only`; past reports remain frozen. Investigation reached the [original bitmap contract](../hardware/display-gpu/builtin-font-bitmap-contract.md). The [first W5 virtual storage integration](../research/virtual-web-install-storage.md) was also checked. Next was the S6 IOM6 behavior unit.

At each unit's end, update next actions and stop conditions for S6/D3/W5 in `project-scope.json`. Do not replace display/web recovery work with continually passing MMIO boundaries. Leave W5's final segment requiring normal boot as a dependency, while proceeding with virtual transfer/failure scenarios that can be done in advance.

## Display-path prerequisites

The current missing-font diagnostic is not a normal stock asset. Even with further initialization, it does not prove normal font, app loop, or successful display. Track these paths separately:

| Path | Evidence to obtain next | Existing evidence / restrictions |
| --- | --- | --- |
| Normal stock font bank | Legitimate distribution source, exact version/hash, original pointer/bitmap contract | Official SDK metrics are not the stock bitmap bank. `font-asset-distribution-research.md` |
| Original built-in font display preparation | Original bitmap callback buffer ownership, release, and rasterization | Representative glyph bitmap callback confirmed. Generic lifetime/natural renderer unknown. `builtin-font-bitmap-contract.md` |
| Integrated display | Actual UI render call → framebuffer content/size → display submission → output adapter | Do not add independent renderer result (D2) as integrated display (D3) |

Maintain separate manifests for diagnostic paths without assets and normal-asset paths. Do not implement a GPU driver before evidence that an actual source hook is needed. Once an external font bank is ready, compare missing-font diagnostic and normal-asset paths under the same input.

## Reproducibility and observation

- Audit historical captures using saved inputs, model hashes, and logs; do not make them depend on the current candidate builder.
- Record component before/after SHA, runtime edits, and pinned image/main hashes for new candidates. Reuse shared runner/JSON plans instead of wholesale rewriting past tools.
- Pin observation during original execution. Prefer reads after stop for additional diagnostics and record observation changes as new execution configurations.
- Matching event prefixes, PC, and counters is evidence within observed scope, not equivalence of all SRAM, scheduling, or physical timing.
- Change progress only when evidence for a higher-level completion criterion is satisfied. Task counts and audit-check counts are not product progress.

## Adoption of bw243 one-off review

Following the [latest review](../project/astra-iom6-direction-review.md), bw242 ends with reset/ready hypothesis delay/failure controls and the first SPI/unknown-peer boundary. Even a time-based implementation does not validate physical delays. Next prioritize the actual receive, validate, and write flow of the recovery owner in W5 damaged-main conditions. Do not interpret retransmission success in host virtual storage as recovery-transport survival. If evidence is insufficient, switch to D3 resolved_font → buffer lifetime → actual renderer caller. Source acceptance repair completed with unit 13/host 15; no additional generic framework or unchanged native rerun.

## bw242 reset/ready limited-unit closure

[EM9305 hypothesis results](../hardware/communication/em9305-reset-hypothesis.md): nominal and delay controls for three originals passed ready and stopped at DCXCTRL setup, SPI commands 0. Two no-response conditions stopped strictly at a separate error-consumption boundary, and off-control exactness was confirmed. First SPI transfer was not reached, so bw242 was deferred. As reviewed, next investigate one W5 damaged-main recovery-owner receive/validate/write flow. If evidence is insufficient, switch to D3 resolved_font → buffer lifetime → renderer caller.

## bw244 recovery-owner investigation

The [new worker fixture](../bootloader/recovery-owner-flow.md) confirmed compiled UART2 authentication/LOAD/CRC/API3 setup → RAM-call entry without main. Scheduler, case, writer, and ROM were not yet connected. Next is one flow preserving M55 RAM context save/restore through writer/callback/stock MRAM wrapper. The difference that the upstream CLI merely warns for pending OTA remains a requirement for an actual-execution hard gate. This is not completion of W5 full recovery or physical installation readiness.

## bw245 M55 RAM writer integration

[Limited body integration](../bootloader/recovery-m55-resident-writer.md) verified four conditions across actual context wrapper → uploaded writer → compiled callback → stock MRAM adapter → virtual ROM write → RESULT. FPCA/FPU/VPR seeds, prequeued UART, and ROM/cache models are explicit; do not assess it as full recovery. Next investigate D3 resolved_font → buffer lifetime → renderer caller. W5 still needs whole-image backup/CRC/vector-last, pending gate, dynamic host, and manager/case integration.

## bw246 font wrapper and renderer boundary

The [new contract](../hardware/display-gpu/font-wrapper-renderer-boundary.md) confirmed original wrapper resolved_font, caller-buffer reuse/capacity rejection/release, and original letter prefix → immediately before actual Ambiq callback. The backend did not execute and data remained unchanged. Next investigate Ambiq target buffer/format/stride ownership and submission arguments. Do not add isolated function preparation as D3 full main/display completion. A Unicorn write-observer mutation was avoided by structuring around protected inputs/read hooks/final differences; original code execution was not substituted.

Later bw268: [original main display/SPI integration boundary](../firmware/main-display-integration-frontier.md). After DCX no-pin latch, execution stops at SPICFG=4 with SPI commands=0. Actual waiting conditions for UI/two display workers were confirmed; message/notification producers were the next analysis targets.

Later bw270: [first IOM6 SPI command](../hardware/power/iom6-first-spi-command.md). Original main in three images requests `CMD=0x201`, TX `81 00`. After FULLDUP configuration, the command remains blocked before transmission, commands=0. Next is a transaction model combining CMD-before-FIFO, full-duplex/TSIZE, and word FIFO.

Later bw271: [SPI word transaction](../hardware/power/iom6-spi-word-transaction.md). Original M55 main in three images completed explicit one-shot `8100/c000` transactions and copied into actual RX buffers. Execution stops at the next request due to budget exhaustion; actual EM9305 state, physical CS, BLE boot, and integrated display remain unverified.

Later bw272: [HCI framing contract](../hardware/communication/em9305-hci-framing-contract.md). After a positive header, the original holds pin 149 low and stops at a new RDY consumer. Initial expected event is `04ff0101`, based on source/manufacturer index. Actual payload, EM9305 state, and BLE boot remain unverified.

Later bw273: [virtual active-event delivery](../hardware/communication/em9305-active-event-transport.md). CS/RDY phase and RX-only were connected, confirming initial event acceptance and wrong-event rejection by three originals. Optional budget 2 was added for the same retention cleanup; default 1 and unknown global inputs remain. Full main/BLE/display/physical-device validation is incomplete.

Later bw274: [first HCI command contract](../hardware/communication/em9305-first-write-command.md). The first packet planned for transmission is `fd01`, an eight-byte read at address `00f04b88`. Actual response is unknown and affects the trim-update branch. Existing RAM/source and an ARM fragment were analyzed without native restart or physical-device access.
