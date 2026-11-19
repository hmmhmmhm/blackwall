# Current G2 emulator capability catalog

Latest completion: [stock 2.4 original bootloader reset → main → 576×288 screen](../bootloader/original-boot-completion-audit.md), 8/8. [Reproduction CLI](../bootloader/original-boot-reproduction.md). This is distinct from actual Boot ROM and full-chipset precision; the history of earlier scopes is preserved below.

## Current acceptance evidence summary

The existing v3 scope and denominator below follow the [dashboard](../project-dashboard.md) and scope v3. **16/16=100% of acceptance conditions are met**; the [final audit](emulator-final-audit.md) compared the current CLI with actual evidence. Distinguish these from the historical figures below.

| Area | Currently verified behavior | Remaining boundary |
| --- | --- | --- |
| bootloader → main → screen | [Stock 2.4 original boot reset → handoff → same-board main/UI/render/576×288](../bootloader/original-boot-completion-audit.md), [reproduction CLI](../bootloader/original-boot-reproduction.md) | Actual Boot ROM, other boot/main combinations, full-chipset precision, and physical hardware unverified |
| Main boot | [Three originals reset → service → UI wait/resume](../firmware/native-main-boot-acceptance.md) | Three families starting main directly; bootloader path limited to stock 2.4 above |
| Screen | [Three originals' UI, font, render, and 576×288 frame](../bootloader/boot-family-first-screen.md), [continuous refresh](../bootloader/boot-family-post-screen-lifecycle.md) | Reference GPU and functional sensor assumptions; physical pixel accuracy unverified |
| Active reset | [Virtual NVIC reset → reinitialization → UI/frame/task return](../hardware/power/active-board-reset-acceptance.md) | Not certification of all non-idle combinations or physical reset |
| Touch | [Three originals' additional input → original UI command/return → scroll](../hardware/sensors-input/active-hud-touch-family-contract.md), each no-input control unchanged | [E11 complete](../research/input-acceptance.md). Additional undeclared gestures unsupported |
| Ring | [Three originals' UART relay → original consumption → UI return and screen](../research/input-acceptance.md), each with a one-second no-input control | E11 declared v1 complete. Direct R1 BLE and arbitrary gestures unsupported |
| Sensor | [Three originals' FIFO/IRQ → natural sensor_hub consumption and numerical result](../hardware/sensors-input/sensor-task-consumption.md), each with a no-input control | E12 v1 complete. Numerical GAF/EDMP fusion and physical accuracy unverified |

To reproduce the latest boot, screen, and input artifacts, use the pinned manifests and audit commands in the behavior documents above. Do not interpret strict stops or API caller diagnostics in older checkpoints as the current natural main state. Other acceptance conditions follow the individual evidence on the dashboard.

## Historical checkpoint records

“Current,” “latest,” and numerical/support tables below refer to the state at each record's time. The current summary is the table above.

bw484 [active-board reset acceptance](../hardware/power/active-board-reset-acceptance.md): Three originals E05 active screen → virtual NVIC reset → original vector/service → new UI/5 frames/task wait resumed; reset 0→1→1, GPU 7→0→7, cache/IMU/peer/UART initialized, ITCM/NOR/FS preserved, fault 0. Existing guards/cache fix reused; measured XOR100/IOM7 shared-gate profile; 13 frozen dependencies/3 semantic negatives; 5 containers absent. E06/M3 complete, 14/16=87.5%, E11/E12 remain.

bw483 [original main boot acceptance](../firmware/native-main-boot-acceptance.md): Directly paired verification of three originals' reset/service return/initial UI → actual empty UI queue receive wait 10 ms after first screen → original callback resume in same TCB (4.755/4.873/4.815 ms). Main/board/model unchanged, six initial SRAM regions exact, 5 frames, fault 0; nine-dependency frozen audit; three semantic negatives/partial-case integration rejected; three containers absent. E05 complete, 13/16=81.25%, E06/E11/E12 remain. Physical hardware/agents/publications 0.

bw482 [three originals' post-screen lifecycle](../bootloader/boot-family-post-screen-lifecycle.md): Stock 2.3 100.107 ms/Faceclaw 100.120 ms, five frames each, serial 3→7, fade-in and sleep entry/exit, fault 0. Originals/device models unchanged; six initial SRAM regions exact. Frozen eight-dependency audit of three families including saved stock24 evidence; two negatives rejected. Four original UI callbacks each and final event-list membership confirmed; direct wait→resume pair deferred to next step. E05 partial, 75% retained.

bw481 [three originals' first screen](../bootloader/boot-family-first-screen.md): Stock 2.3 and Faceclaw original reset → touch/UART → normal UI return → 31 lists/120 draws → completed 576×288 source. Raw SHA matches stock24; six initial SRAM regions exact/guard; fault 0; independent frozen nine-dependency audit/two semantic negatives rejected. Post-first-screen lifecycle for the two families incomplete; E05 partial, 12/16=75% retained.

bw480 [post-first-screen lifecycle](../bootloader/post-screen-boot-lifecycle.md): Reproduced first frame of stock24 pinned model/original → 100.695 ms; five original completed frames, fade-in, zero missing, sleep entry/exit present, fault 0. Schema2 evaluation and independent audit of three semantic negatives/eight frozen dependencies. E10/M6 complete, 12/16=75%. E05 three originals, reset, additional input/sensor consumption, and physical hardware incomplete.

bw479 [first natural dashboard](../hardware/display-gpu/first-native-dashboard-frame.md): Directly inspected stock24 original main reset → virtual touch/peer → UI/glyph/render/submit → packing-completed 576×288 guest source. Functional sensor and GPU reference profiles; main unchanged, initial SRAM exact, fault 0. E09 complete, 11/16=68.75%. Full boot, continuous frames, physical hardware, and identical integration on other originals incomplete.

bw478 [SDK 2.0.0 actual source review](../research/icm45608-sdk-source-review.md): Preserved user ZIP, extracted 368 text files, reviewed GAF examples. 45 of 46 sensor drivers match existing public blobs after LF normalization; only version rc1→2.0.0 changed in the other. Official GAF example cold input/output and ICT1531x source added to evidence, not a new implementation of full GAF calculation. Separate functional model design recommended; implementation/new ARM/physical hardware 0; 62.5% retained. Browser Skills Chrome connection confirmed.

bw476 [normal GAF execution material dependencies](../hardware/sensors-input/gaf-family-guide-and-access-evidence.md): Newly downloaded public official AN-000478 rev1/54 pages; reviewed target differences, text, and rendering. Target ICM45608 SDK still requires login. GAF requests 2/4 calculation, ISA, and independent results unavailable. Model changes/new ARM/physical hardware 0. Recorded common gaps and resumption inputs for six remaining conditions; stopped repeating the same diagnostics; overall 10/16=62.5% retained.

bw475 [FIFO → pulse → GPIO38/IRQ57](../hardware/sensors-input/imu-fifo-gpio-irq-integration.md): Verified original INT1 low3=1 push-pull/active-high/pulse, correcting initial latch assumption. Original setter/WM10 → GPIO38 → original ISR/callback/exception return → separate original consumer 10 packets; 2252-byte ring exact to existing formula. 36 checks including 8/100 µs pulses; optionalWatch on/off six SRAM regions/WORK exact; stored audit 103/12 containers absent. Gate 0; natural task consumption and GAF incomplete; overall 62.5% retained.

bw474 [original FIFO configuration → consumption](../hardware/sensors-input/imu-fifo-native-configuration.md): Connected shared CFG2/ODR, timed IREG, atomic bank. Stock24 original setter R0=0/frame 0→32/WM10 → original consumer 10 packets/320 bytes; 2252-byte ring math exact; Watch on/off initial/post-configuration/final SRAM and WORK exact. Configuration 32, legacy raw 70/228, transport 176, ODR 1278, threshold 27, saved-input audit 109/21 containers absent. Synthetic API diagnostic; natural GAF/GPIO/root full return incomplete; overall 62.5% retained.

bw473 [raw32 parser → M55 consumption](../hardware/sensors-input/imu-fifo32-parser-and-transport.md): Three originals parser/callback 120 + codec 3 isolated; ES valid/offset/size 6, 9 and endianness confirmed. Raw32/cap64 model; final 70/legacy 228, 176, 27. Stock24 M55 WM10/320 bytes → callback/ARM decoder 10 times; 2252-byte ring math exact; Watch control SRAM/WORK exact; codec output 80 bytes cross-exact; audit 65/eight containers absent. Host frame configuration/guest configuration/GPIO/GAF incomplete; 62.5% retained.

bw472 [actual FIFO configuration discovery](../hardware/sensors-input/imu-fifo-guest-configuration-contract.md): Confirmed three originals' enable branch requests ES0/ES1, 32 bytes, WM10/stop-on-full and setter frame 32. Setter 908 bytes identical; isolated ARM 186 (ABI stub)/audit 37; new M55 0. Next: raw32/ES callback contract → shared CFG2/timed IREG/original configuration → IRQ. Raw16 is a separate experimental profile; GAF incomplete; 62.5% retained.

bw471 [FIFO threshold → upper-layer consumption](../hardware/sensors-input/imu-fifo-threshold-status.md): Default off; successful-enqueue-based latch/generation/R-C transactions and logical IRQ. Actual IOM final 27/legacy 176/raw 228; original stock24 upper status → count 2 → data → parser/callback, two samples/four transactions, source-owned ring exact; Watch on/off SRAM/WORK exact. Audit 68/12 containers absent; resetdone 1-byte collision failure preserved. Guest configuration/GPIO/GAF and full root return incomplete; 62.5% retained.

bw470 [original RTOS FIFO transport](../hardware/sensors-input/imu-platform-fifo-m55.md): Full-board original Sensor Thread/PSP FIFO API → mutex acquire/IOM preparation/HAL/cleanup/release → parser/callback, two samples stored. Gate 0/IRQ mask unchanged; actual count 2/data 32; 2252-byte ring exact; Watch on/off final SRAM/WORK exact; audit 61/four containers absent. Incorrect-copy failure preserved; natural IRQ/status/GAF incomplete; 62.5% retained.

bw469 [original M55 HAL → FIFO → parser](../hardware/sensors-input/imu-hal-fifo-m55.md): Stock 2.4 isolated synthetic caller returned normally in six original HAL calls and seven including parser; actual IOM six commands/three transactions/two packets consumed; 2252-byte ring raw/float/time exact; other SRAM control exact; audit 29/six containers absent. Natural main/RTOS upper layer/GAF incomplete; 62.5% retained.

bw468: The [optional FIFO I²C adapter](../hardware/sensors-input/imu-fifo-i2c-transport.md) connected actual IOM length/splitting/termination. Confirmed 176 checks per endianness and preservation of stock 2.4 cold off/on baselines. Original main sample consumption and guest flush/IRQ/GAF integration remain incomplete.

bw467: The [raw FIFO storage component](../hardware/sensors-input/imu-raw-fifo-storage.md) is default-off and independent Renode machinery. 228 checks covered raw16/2 KB, packet count, full transaction consumption, and flush/reset; it was not yet connected to identity peer/IOM/GPIO or natural main. This is distinct from normal GAF support.

bw458 [public Ring scenario](../hardware/communication/ring-public-scenario.md): Independent 62-file/63 MB workspace; three originals/registered candidate CLI passed; actual ARM source 4→5 regression detected exit 1 despite UI entry. Five new native/five saved audits (zero additional VMs)/10 CLI/45 aggregate; zero old-asset reads; bw457 six SRAM regions exact. UI return/pixels/GAF incomplete; 10/16=62.5% retained.

bw457 [Ring → app/UI wake](../hardware/communication/ring-app-wake-contract.md): Stock 2.4 actual 108/ACK → original app role 255→4/tick 5288 → app 1 request/single reply → ui_task callback entry. IOM7 XOR100 boundary identified; existing shared IOM profile reused; five SRAM prefixes exact; audit 45. UI return/pixels/GAF incomplete; 10/16=62.5% retained.

bw456 [three originals' ring and duplicate suppression](../hardware/communication/ring-family-and-duplicate-contract.md): Two new old2 native runs/stock24 reused; original relay/queue/ring and CFW actual fallback confirmed; audit 60. Stock24 two reports/60 bytes → two receivers/one slider, tick 1000 retained; audit 27. New models 0; UI/screen incomplete; 10/16=62.5% retained.

bw455 [Ring relay input](../hardware/communication/ring-input-ingress-contract.md): Confirmed stock 2.4 virtual opposite-temple UART0 → actual ring task → source 4/code 1/caller return. Source 3/isolated M7 190/natural M55 audit 23. Direct R1 BLE, other-original native runs, and subsequent UI/screen incomplete; E11 remains partial.

bw454 [three originals' repeated input](../hardware/sensors-input/touch-repeat-family-contract.md): Confirmed two GPIOs → two original handlers, distinct slider arguments, and caller return for stock 2.4/2.3/Faceclaw. Same device model; audit 72; stock 2.4 reused. App/UI, ring, and pixels remain separately incomplete.

At this checkpoint overall acceptance was **10/16=62.5%**. For the latest status follow the [dashboard](../project-dashboard.md) and scope v3; scores and next steps below are historical. The latest input path was [bw452 three originals' double-click → app 1 natural UI callback](../hardware/sensors-input/touch-wake-family-contract.md). Stock 2.4 callback return was confirmed in the bw448 HP interval; stock 2.3/Faceclaw reached entry. [bw453](../hardware/sensors-input/touch-repeat-frame-lifecycle.md) confirmed two independent stock 2.4 reports → original handler/slider/caller return. Default-off reload, synthetic 86/existing 59 values identical, audit 30. Repeated input on other originals, second UI, render/screen, and gesture/ring scope incomplete; E09/E11 partial.

bw430 [request 4 and preceding WDT](../hardware/sensors-input/gaf-after-first-timeout.md): After the first stock 2.4 timeout, original request 4 → watchdog request on the second 66808th poll preceded cleanup. First core/four SRAM regions exact; audit 26/three counterexamples; no actual reset. Stopped expanding frozen variants; next E16 common tools/normal calculation evidence; overall 8/16=50% retained.

bw429 [original first GAF timeout](../hardware/sensors-input/gaf-timeout-cadence.md): Stock 2.4 completed original 200000 polls → actual wait/helper/setter return R0−4 under the interval HP profile. WDT active, guard fault 0, transition state/prefix exact; audit 24/three counterexamples. Normal calculation and subsequent initialization incomplete; 8/16=50% retained.

bw427 [GAF delay and virtual time](../hardware/sensors-input/gaf-delay-clock-contract.md): Confirmed minimum 811 instructions for original 5 µs request take 81.1 µs at current 10 MIPS. Distinguishes HAL's 3 cycles/loop contract from virtual MIPS. Four SRAM regions/existing results exact; audit 22/three counterexamples; CPU/WDT/timeout unchanged. Next independent verification of separate timing profile; overall 8/16=50% retained.

bw418 [three originals' reset reprocessing](../hardware/power/reset-restart-version-profiles.md): Stock 2.3/Faceclaw also succeeded in reset → service → new virtual connection/ATT → RTC commit 1 under the same shared model. Stock24 reused existing artifacts; two new native runs/audits 30, 31, 31. E06 partial until independent post-reset protection/lifecycle verification; 8/16=50.0% retained.

bw417 [post-reset app reprocessing](../hardware/cpu-memory/cpu-retention-preparation.md): Stock 2.4 original reset → RET/WFI → service reinitialization → new connection/ATT → RTC commit 1 succeeded. Renode sleep 21.2058 ms/IRQ32 prefix confirmed; event overflow and unverified physical timing/full boot preserved. E06 partial pending other originals/lifecycle audit; 8/16=50.0% retained.

bw416 [CPU retention setup](../hardware/cpu-memory/cpu-retention-staging-contract.md): Analyzed 0x22 configuration in three originals and confirmed natural return of the stock 2.4 post-reset setup function. Only optional register storage implemented; subsequent deep-sleep preparation, entry/wake, and app return incomplete. Overall 8/16=50.0% retained.

bw415 [system reset during original execution](../firmware/original-main-system-reset.md): Confirmed stock 2.4 actual ATT processing → NVIC input → original vector/SP re-entry and 20 ms initialization. Subsequent CPDLPSTATE 0x22 causes strict stop; E06 partial, 8/16=50.0% retained. SRAM 204-byte difference/RTC epoch return are separate state-lifecycle boundaries.

bw414 [system reset foundational contract](../research/system-reset-boundary-contract.md): Reproduced pinned engine BASEPRI cache persistence on synthetic M55 and confirmed IRQ resumption with a separate opt-in model. Original G2 app post-reset return unverified; E06 partial, 8/16=50.0% retained. Next: declare RAM/NOR/RTC/ITCM reset domains and integrate original board.

bw413 [E14 communication failure acceptance complete](../research/peer-failure-acceptance.md): Checked three originals × three pinned categories: disconnect, bad CRC, and delay-timeout-reconnect. Strict response, original task/CCB/IRQ, generation reset, and credit restoration verified. Normal GAF/full app, physical hardware, and absence of effects from every observer remain unverified; **overall 8/16=50.0%**.

bw399 [scoped observer suspension](../research/scoped-observer-suspension.md): Five pinned-original 500 ms pairs had exact full SRAM/R0–15/instruction counts, with diagnostic time −100 ns preserved. Median execution interval 17.82→1.77 s; total 61.12→45.94 s. Three owned callbacks opt-in; defaults/guards/16 conditions unchanged; overall 7/16 (43.8%).

bw398 [host bottleneck identified](native-execution-bottleneck.md): Observed time concentrated in native breakpoint management of the actually busy CPU thread; compared increased hits on three general IOM hooks. Protection policy unchanged; no improvement/speedup claimed. Next: selective suspension of owned callbacks and equivalence/performance comparison. Overall 7/16 (43.8%) retained.

bw397 [frozen EDMP core fault](../hardware/sensors-input/gaf-frozen-core-fault.md): Unit 64/frozen JSON values identical, raw order differed. Original main request 2/busy 1643; host limit prevented reaching timeout, semantic false/deferred. Next: profile execution bottleneck; no bypass of protections or repetition. Overall 7/16 (43.8%) retained.

bw395 [E08 storage failure acceptance complete](../research/storage-failure-acceptance.md): Audited the 13 pinned scenarios in existing acceptance wording and updated to **7/16=43.75% (displayed 43.8%)**. Additional ARM 0; frozen exact. Observed SRAM 35/270-byte differences and unverified full app boot/physical recovery remain documented. Figures below are historical at each task.

bw394 [per-original erase failure](../bootloader/peer-boot-nor-erase-timeout.md): Ten new native runs, five existing reused. Per-original NOR unchanged/new formatter controls. Faceclaw fault observer SRAM 35-byte difference preserved as false. Audit 124/frozen exact; E08 partial, 6/16 retained. Next: complete judgment of pinned E08 scenarios.

bw393 [three originals' program timeout](../research/peer-runtime-nor-program-timeout.md): Confirmed stock 2.3/Faceclaw actual error 4 → FAL 0/FDB 0, no NOR write, new CPU reads old value. Three-way integration audit 88/frozen exact; prototype lacking diagnostics preserved separately. E08 partial, 6/16 retained. Next: remaining per-original erase controls and completion audit of all pinned E08 scenarios.

bw392 [kvTime schema/version contract](../hardware/cpu-memory/kvtime-schema-version-contract.md): Original logs and instructions establish byte 0=version/expected 3. Three originals ARM 108; valid-CRC version 4 native initial load in three images (two new, one reused); subsequent CPDLP22 stop; full compatibility unknown. E08 incomplete, 6/16=37.5% retained. Next: close unexecuted integrated failure evidence for stock 2.3/Faceclaw.

bw391 [nonzero NOR erase timeout and new reset](../bootloader/boot-nor-erase-timeout.md): Actual original erase error 4 → FAL 0 → FlashDB 0; pattern preserved, busy read strict. Fault off/on SRAM/NOR exact; new-process normal formatter final NOR/SRAM exact to normal on. Normal on/off SRAM 270-byte difference preserved unresolved. E08/full boot incomplete; 6/16=37.5% retained.

bw390 [erase error propagation](../hardware/cpu-memory/nor-erase-error-propagation.md): Three originals ARM 33 showed pre/post-command timeout errors 3/4 lost as adapter 0 → FlashDB 0. Also verified 4 KB alignment/round-up, two normal sectors, readonly/out-of-range controls. Synthetic peripheral ABI/new native 0; actual erase recovery incomplete; overall 6/16=37.5% retained.

bw389 [actual runtime program timeout](runtime-nor-program-timeout.md): Observed poll 1 → NOR 4 → adapter 0 bytes → partition 0 → FlashDB 0 in original main with pinned GAF. Unlike the new RAM value, NOR stayed unchanged and new main read the old value. Legacy 02ae failure preserved separately; GAF service/CPU power strict retained. E08/app recovery incomplete; 6/16=37.5% retained.

bw388 [NOR timeout and FAL propagation](../hardware/cpu-memory/nor-timeout-fal-propagation.md): Three originals ARM 21 confirmed loss of NOR error 4 → adapter 0 bytes → partition 0 → FlashDB wrapper 0. Out-of-range/readonly reject 3. Synthetic peripheral/lifecycle ABI, new native 0; not evidence of full app recovery. Next: actual virtual program-timeout integration control. E08 partial, 6/16=37.5% retained.

bw387 [restart control before/after commit](../hardware/cpu-memory/nor-program-commit-boundary-pair.md): Original main verified selection changing old→new value from a single new-state byte difference 7f→3f. The new value was read even though old-record cleanup was incomplete. One stock 2.4 atomic-completion boundary; full recovery/E08 incomplete, 6/16=37.5% retained. Next: write/erase error propagation contract.

bw386 [original program interruption → restart](../hardware/cpu-memory/nor-program-interruption-restart.md): Stopped at actual sixth write WIP with 5/40 bytes completed; new main read the old record. Even with the complete payload, an uncommitted new state was not selected. One stock 2.4 boundary of the atomic-completion model; full recovery incomplete. E08 partial, 6/16=37.5% retained.

bw385 [corrupt NOR reload policy](../hardware/cpu-memory/kvtime-corruption-reload-policy.md): 48 isolated cases across three originals and three actual stock 2.4 resets. FlashDB CRC mismatch caused initial values to be rewritten; internal CRC corruption/type 4 with correct outer CRC was loaded into RAM. Observation, not recovery success; E08 partial, overall 6/16=37.5% retained. Next: actual program/erase failure and interruption contracts.

Latest bw384 [kvTime persistent storage and restart read](../hardware/cpu-memory/kvtime-persistent-restart.md): Original main in a new process reread values written to virtual NOR by three originals. Without transferring previous SRAM, verified storage range, neighbors, and original input preserved; E07 complete, **overall 6/16=37.5%**. Subsequent CPDLPSTATE `0x22` write stops as unsupported; full boot/E06/E08 incomplete. Checkpoint figures below are historical.

Latest bw383 [regression state propagation](runtime-candidate-state-lineage.md): The extra four bytes were identified as kvTime zone/CRC and log argument SP storage. Source-derived five-byte oracle comparison passed; candidate app_state failure remains. Next: actual kvTime storage/restart contract; E07/E08 and overall 5/16 unchanged. States below are historical at each checkpoint.

Latest bw382 [registered candidate runtime and comparison](runtime-registered-candidate-integration.md): Actual stock/marker candidate passed ATT → RTC; detected app_state failure in two-byte regression candidate. Unexpected four SRAM bytes unexplained and comparison remains false. E15/E16 partial, overall 5/16 unchanged.

Latest bw381 [GAF calculation-effect assessment](../hardware/sensors-input/gaf-derived-effect-feasibility.md): Host setter's subsequent read is four bytes at 0x5bc, but input is synthetic and evidence for EDMP calculation insufficient. bw379 control audit closed; calculation remains unsupported. Stop repeating the same control probe and switch to E04 candidate/E13 common execution and comparison. Overall 5/16 retained.

The then-current overall flow, scope, and next pass judgment follow the [one-time bw380 Astra review](emulator-scope-audit-bw380.md). Overall 5/16=31.25%, 11 conditions remain, and the original 16 acceptance conditions are retained. bw379 partially observed request control, calculation unsupported, final audit not closed. Checkpoint figures below are historical.

Baseline: bw342 scope v3; previous main baseline bw338; stored task audit bw339; display queue test bw340; additional API-based native activation diagnostic bw341; original app dispatch bw344; JBD status transaction and renderer entry bw345; GPU runtime wake, shape/quad reference profiles, actual nonzero guest screen, and texture conversion boundary bw346. Normal natural main is the bw353 boundary at the first service request after explicit GAF/trim and 225-byte storage. bw358 is a separate initial-readiness/ID-failure profile. Evidence from one layer does not replace another.

| Area | Verification at that checkpoint | Product evidence absent then | Acceptance then |
| --- | --- | --- | --- |
| CPU/execution | Renode 1.17 M55 basic instructions, exceptions, IRQ, memory guards. Pinned three originals' main reset execution | Not certification of full M55 ISA/security/timing accuracy | E02/03 complete, E05 incomplete |
| Current main | Natural native: 29 original RTOS tasks/image; sensor_hub reads explicit GAF/trim, stores 225 bytes bias/GAF, then stops at first GAF service request. One unlinked TCB candidate excluded from active tasks | Normal app event handling and sustained operation | E05 |
| Memory/clock/power | Functional models for observed paths, explicit initial values, request/status; unsupported access stops | Actual voltage, power, physical cache, all sleep/reset | E05/06 |
| Persistent storage | Three originals kvTime → NOR commit → reread by new-process main; write neighbors/original preserved | Full app runtime reset, storage failure/interruption, version mismatch | E07 complete / E06/08 incomplete |
| Bus/time/IRQ | Native UART, timer, IOM4/6 and observed SPI/I2C transactions and IRQ paths | Generalization to all bus instances/commands, arbitrary DMA/timing | E05/12/13 |
| BLE controller | bw375 E13: three originals reset then virtual connection → GPIO/IRQ → H4/ATT → EUS/TPL → original task → RTC application/consumption return. 25 native each, advance 20-second budget, roles/waiting output declared, no API caller/PC/TCB/SP seed | Limited to local time setting; full UI, disconnect/delay, reconnect, outbound sync delivery incomplete | E13 complete / E14 partial |
| Touch | Three originals' app consumption and idle/code4 discard. Actual double-click → original UART request/single reply timeout IRQ → three originals' app1 callback entry. Faceclaw actual hook fallback. 2.4 callback return supported by separate HP interval evidence | Old2 callback return, render/frame, valid custom-state path, additional input lifecycle, gesture/ring | E11 |
| IMU | Expected ICM45608 source, virtual identity/reset/auxiliary MAG/ODR/EDMP/WOM/powersave and explicit GAF 41-field 153-byte read, 225-byte bias/GAF storage | GAF service calculation/completion, dynamic sample/FIFO/IRQ consumption, physical ROM values | E05/12 |
| GPU/font | One synthetic M55 run: original draw → submit → diagnostic GPU → guest 64×32 A/W. Later synthetic context test of IRQ/PendSV/wait | Full 576×288 natural main UI, general GPU ISA, complete font bank | E09/10 |
| Display queue/UI activation | M7 actual send/receive + API-driven native M55: original scheduler UI/display resume and actual mode 0→1. No forced IRQ/TCB/stack/mode or callee stubs | API stimulus inserted by test caller. Wire input, type-3 first frame, natural main completion incomplete | E05/09/13 |
| App processing/render entry | API-driven native three originals: explicit virtual JBD05/35 responses, registered callback, actual ambiqdraw task draw/target calls, two error response controls | Native three originals: 11 lists/106 draws, 11 IRQ assert/ack, nine white dots on nonzero guest screen. Explicit area-reference advanced to 14 lists/142 draws, completion 12/ID3. Subsequent 102-word texture, full UI/frame wrapper, natural main incomplete. Physical MSAA/status values unverified | E05/09 |
| New CFW | Three existing pinned images and declared raw-main candidate registered; vector/extent/observer anchor checks; same runner execution/saved audit | Comparison of new candidate's app features, screen, input, and communication behavior | E04 complete / E15 partial |
| Tools | Pinned plan, separate execution/semantic judgment, saved audit, source/asset hashes and stopped snapshots | Single developer command for scenario, screen, comparison, reproduction | E16 |
| Virtual phone/opposite side/case | Virtual phone/controller path for time setting and original app behavior confirmed; some protocol/recovery unit mocks | Local path roles/waiting output declared. Opposite temple/case runtime and outbound delivery, disconnect, delay, errors unverified | E13/14 |
| Boot/OTA | Limited handoff before boot → main reset and virtual transport/write unit tests | Full cold boot from ROM, original execution on both CPUs/case, full OTA integration | Separate extension profile |

Additional diagnostic commands and boundaries follow [original M55 activation](../hardware/display-gpu/display-activation-native-diagnostic.md). In the API diagnostic, main is normally held before the IMU getter, then a test caller is inserted. Distinguish this from the latest strict boundary of natural main below.

The then-current scope, flow, and score judgment follow the [bw376 review](emulator-scope-audit-bw376.md). The subsequent [bw375 device ATT time setting](runtime-att-time-device-ingress.md) completed E13, yielding overall 5/16=31.25% (displayed 31.2%). Distinguish the initial stock24 audit failure from the separate successful saved audit.

bw377 [peer communication failure](runtime-peer-failure-contract.md): Three originals passed immediate disconnect cleanup/app close and bad TPL CRC rejection; stock24 passed 1 ms delayed input. Long 1000 ms wait stopped at 1.2286 ms at the older runtime IMU/IOM4 boundary. Integration with latest GAF model comes first; full E14 and timeout/reconnect incomplete.

bw378 [communication/GAF integration](runtime-gaf-profile-integration.md): Connected pinned IMU component to the same device session and confirmed three originals' GAF 41 fields/153 read and 225 write. Earlier old-model boundary resolved; now stops at first GAF service. The approximately 171 ms boundary is not completion of normal boot, calculation, or long timeout.

## Initial baseline profile and reproduction

Pinned mains: stock24, stock23, Faceclaw38. Original raw hashes, capture paths, and audit pins are in private `simulator/emulator-scope-baseline-01/report.json`. Images and device secrets stay outside Git.

- Engine: Docker Renode 1.17 M55 image `sha256:e840c2b9a83dbf9be060047839aaaf6d434e7d4c52635191319afc14f4217649`.
- Latest plan: private `simulator/imu-clock-variation-plan-01.json`.
- Capture: `simulator/imu-clock-variation-main-01/{stock24,stock23,cfw}`.
- Current checks: `simulator/imu-clock-variation-source-01/{verification-manifest.json,native-verification-01.json}`. Earlier getter audit is preserved in `imu-gaf-parameters-saved-audit-01/`.
- Current stop: first service-request strict boundary (payload 7c000402) after explicit trim 0x85 read and 225-byte bias/GAF storage. Standard native HAL PC is stock24 `0x58236c`, old/CFW `0x57b014`. This is not full boot success.
- ROM result fixtures and physically unverified values are specified in the plan/manifest above and the [GAF getter document](../hardware/sensors-input/imu-gaf-default-getter.md). Unconfirmed values are not treated as actual chip defaults.

Rechecking saved artifacts is distinct from a new native run. The command below reads the existing capture, writes a new audit folder, and does not access the glasses.

```sh
python3 tools/run_native_candidate.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  "$HOME/Library/Application Support/Blackwall/simulator/imu-clock-variation-plan-01.json" \
  "$HOME/Library/Application Support/Blackwall/simulator/imu-clock-variation-main-01/stock24" \
  --case stock24 --audit-existing --audit-output <new-private-audit-path>
```

The pinned profile's [E16 development tools](../project/development-tools-acceptance.md) were completed in bw438. The common runner for deep model experiments is `tools/run_native_candidate.py`, which derives frozen original-reset inputs. Distinguish the verification scope of a new deep profile from the supported scope of the pinned E16 scenarios. New runs require a new folder, pinned plan/model/observation policy, finite execution budget, and process termination confirmation. Unknowns in the latest profile are not hidden to manufacture app success.

Evidence classifications: **natural native** executes the original main reset path; **synthetic M55** executes original functions with a synthetic caller/context; **isolated M7** is a standalone Unicorn function; **source-only** is analysis without execution. **Unsupported** is a boundary rejected during execution; **unknown** lacks evidence for a value or behavior. Physical-device verification is separate and currently absent.

The latest API content observation, saved audit, and next dependencies follow [original app processing and first render entry](../hardware/display-gpu/ui-content-render-ingress.md). The API diagnostic baseline is preserved; the normal natural main's explicit GAF/trim profile follows bw353.

bw345 checkpoint: [JBD status transaction and renderer task](../hardware/display-gpu/jbd-display-status-and-render-task.md). API checklist M4 complete, but the natural main IMU strict baseline and overall acceptance 3/16 remain.

The bw346 initial checkpoint [GPU runtime wake and command packet](../hardware/display-gpu/gpu-runtime-wake-and-command-packet.md) confirmed three originals' submission/ring functions and 24-word lists in guest SRAM. Doorbell unsupported; GPU consumption, submission completion, and pixels unconfirmed.

Latest evidence and limits for the shape stream and first nonzero surface follow [original shape stream](../hardware/display-gpu/gpu-native-shape-stream.md). Captures were read from actual guest RAM; API diagnostics are not interpreted as natural main completion.

The selectable [quad reference profile](../hardware/display-gpu/gpu-quad-coverage-contract.md) must be explicitly enabled. Default strict rejects quads, and analytic coverage is not reported as equivalent to actual MSAA.

The display-conversion [original list production contract](../hardware/display-gpu/gpu-packing-producer-contract.md) verified 102-word/three-image agreement with isolated M7 auxiliary execution. This is not GPU sampling, actual converted pixels, or new natural main success.

Subsequent [sampling source comparison](../hardware/display-gpu/gpu-sampling-source-boundaries.md): Identified a bit 29 representation difference between official VG1000 material and Apollo headers. Other IP documentation is not treated as verification of Apollo half-pixel behavior; inputs distinguishing eight hypotheses were prepared. No GPU pixel execution evidence was added.

[bw349 IMU consumption analysis](../hardware/sensors-input/imu-parameter-consumer-prefix.md) is an isolated M7/ABI-stub layer. Faceclaw guard ran without a stub and preservation of 153 bytes in the first setter segment was confirmed, but the native baseline remains before IMU 02ae.

Latest bw349 [GAF configuration contract](../hardware/sensors-input/imu-gaf-configuration-contract.md): Addresses, widths, and offsets of 41 public TDK fields match three originals, and a sourced default-value profile was prepared. All 51 setter/24 public-default scenarios and frozen agreement were confirmed, but runtime_enabled=false and physical=false; natural main/peripheral model unchanged.

The latest natural main [GAF getter](../hardware/sensors-input/imu-gaf-default-getter.md) is a native run explicitly selecting source-derived virtual inputs. It inserts no API caller and is not completion of full initialization/app/UI. With the option off, the previous 02ae boundary remains.

The original GAF service [request, wait, and failure contract](../hardware/sensors-input/imu-gaf-service-contract.md) consists of 132 bw354 isolated M7/synthetic I/O scenarios. Since it attempts subsequent writes even after timeout, progress and success are distinct. No EDMP calculation, new native run, or model change; natural main baseline is bw353.

[bw356 candidate registration](../firmware/firmware-candidate-registration.md): Verified a raw test candidate with new hash and length on the actual same M55 runner, completing E04. Overall 4/16=25% and API checklist 3/6 retained. The marker fixture is not a new CFW user feature and does not imply E15 feature comparison or natural main UI completion.

[bw357 identity failure path](../hardware/sensors-input/imu-identity-failure-native.md): Confirmed attempts to configure INT1/EDMP after actual driver return −1 in three originals. Removed the FSYNC prerequisite from the explicit INT1 fixture while retaining rejection when unspecified or during reset. ID0 failure stops at unreset IPREG_MISC; upper initialization return/app start unverified. Normal ID81 stock 2.4 control is exact for existing CPU/full SRAM/existing event projection. This separate failure profile does not replace the canonical GAF service boundary of the three normal images.

[bw358 initial indirect readiness profile](../hardware/sensors-input/imu-initial-indirect-profile.md): Default unknown retained; pre-reset access allowed only in selected virtual state. All three originals advanced to 225-byte configuration/first GAF service after ID error, distinguishing initial driver error from subsequent local state 0. Normal/disabled controls exact; 5051 checks. Physical initial ready, full initialization, and UI unverified; does not replace the canonical normal three-image baseline.

[bw360 IOM4 NAK error](../hardware/power/iom4-nak-error-recovery.md): Added one selected CMD address-phase NAK and recovery clock storage. Three originals' natural execution stops strictly at 7ca272 after NAK on first GAF request; upper return/app unconfirmed. Isolated HAL 36, existing 804 regression, direct 17/default 82, audit 4; final default control CPU/full events/full SRAM exact. Does not replace normal canonical bw353, and no further error variants at the same unsupported boundary are added.

[bw361 peer reply → UI contract](../hardware/display-gpu/ui-peer-reply-ingress-contract.md): Verified in 51 isolated M7 runs across three originals that original master callback passes an existing request's app/payload to UI queue/ring on reply 2. Current context has no corresponding display reply pending and slave channel 2 is unregistered. Synthetic request/descriptor, final callback return, actual wire, and normal request production unverified. Matches existing 81/72 reports; natural main/GAF state unchanged. Next: connect normal request production, sync byte parser, and actual transport boundary.

[bw362 original request/byte parser](../research/sync-request-parser-contract.md): Original allocator/API generated actual ID/correlation record/frame and original receive/parser/callback/free → UI queue/ring verified in 27 normal cases. Nine with same ID and different channel accepted; 45 error cases hit an isolated mapping omission of existing TIMER14, leaving final error return/recovery incomplete. UART0 DMA TX boundary confirmed; next connect existing Renode UART0/Timer14 and actual RX IRQ/task. Isolated API caller/transmit leaf incomplete, native 0, natural main unchanged.

[bw363 UART0/TIMER14 M55 integration](../hardware/communication/sync-uart0-native-diagnostic.md): Verified actual DMA frame, IRQ, original Sensor task/stack return in six transmit/CRC cases across three originals, and receive return after header CRC error branch/TIMER14. Model/initial inputs/main unchanged; six saved audits/frozen exact; nine negatives. Original API caller/direct receive API input retained; UART0 RX IRQ/task path and natural main/GAF incomplete.

[bw364 UART0 RX device ingress](../hardware/communication/uart0-rx-device-ingress.md): Confirmed three originals' error pair FIFO/IRQ/ISR/actual receive task/parser and original return point. Normal reply stops strictly at displaydrv_mgr_task IOM7 initialization. RX timeout for isolated short reply, error frames, and physical timing unsupported; API transmit caller retained; natural main unchanged.

[bw366 normal RX → MSPI0 → UI](../hardware/communication/uart-rx-display-mspi0-integration.md): Existing pinned state component/5a01 verified three originals' receive return point, UI delivery, and pending clearance, plus same-model CRC error control. Root request production, short timeout, natural main/full screen incomplete. 9001 recovery preserved at GPU power 40020080 strict boundary.

[bw367 original request producer](../hardware/display-gpu/display-request-root-contract.md): Verified serialized TPL input → registered callback → SendDataToBoth → actual transmit queue in 53 isolated cases across three originals. Distinguished Faceclaw EUS hook/fallback/F0 differences using original ARM. UART task/ID production, BLE device input, service app/display, and natural main incomplete.

[bw368 original task request and DMA production](tpl-native-request-production.md): Verified across three originals that original UART task produces ID/frame from TPL input and caller returns on original stack. Device model/main unchanged; manual node/start/chunk/finish removed. EUS/ATT/controller, app service/display, and natural main incomplete.

[bw369 EUS/ATT integration prerequisites](../hardware/communication/eus-att-device-ingress-contract.md): Verified three originals' ATT groups/permissions/dispatch and DM lookup in 41 scenarios. Snapshot has no active connection, so ATT dispatcher drops before EUS. Faceclaw's actual registered callback is AN wrapper 7d5924, falling back to original EUS for normal input. Next: controller runtime event → original connection state creation, without forcing host security/active flags.

The latest overall workflow review follows [bw370 scope and next completion conditions](emulator-scope-audit-bw370.md). E13 first establishes the app terminal contract; TPL data transmission and display requests are not automatically connected. Overall 4/16=25.0% and existing 16 conditions retained.

[bw371 TPL service app contract](tpl-service-app-terminal-contract.md): Verified local ble_msgrx → service 80 time-state update in 15 isolated cases across three originals. Original decoder distinguished field128/field16; complete consumption reaches RTC 40004800 boundary. First compare existing RTC model; natural task/ATT/final response remain incomplete.

[bw372 original BLE task time setting](tpl-time-native-rtc-consumption.md): Verified on three originals' M55 TPL API → original ble_msgrx preemption → RTC commit 1 → consuming caller return. Model source/main unchanged; existing RTC write profile selected. Actual ATT input/natural GAF incomplete; overall 4/16 retained.

[bw373 connection event/GPIO contract](../hardware/communication/hci-connection-complete-ingress-contract.md): In 33 isolated cases across three originals, pinned H4/HCI fields, actual DM callback, and GPIO117/IRQ59/original WSF notification. Next connect existing peer runtime event and GPIO pending/IRQ/clear. CCB creation/device input/native unverified in this research; overall 4/16 retained.

[bw374 runtime device connection](../hardware/communication/em9305-runtime-event-gpio-ingress.md): Connected three originals' M55 GPIO117 IRQ59 → SPI/HCI → ble_wsf → CCB creation without API caller/CPU register seed. Default-off CPU/53 observations/full SRAM exact. Next: ATT app data → time-setting terminal value on the same connection; overall 4/16 retained.
