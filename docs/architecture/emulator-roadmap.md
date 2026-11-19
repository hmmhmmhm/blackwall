# G2 firmware test emulator roadmap

Latest completion: [stock 2.4 original bootloader reset → main → 576×288 screen](../bootloader/original-boot-completion-audit.md), 8/8. [Reproduction CLI](../bootloader/original-boot-reproduction.md). This is distinct from actual Boot ROM and full-chipset precision; the history of earlier scopes is preserved below.

bw490 [final audit](emulator-final-audit.md): Compared actual evidence and scope for the existing v3 16 conditions. Confirmed reaudits of boot/reset/input/sensor/storage and peer failures, and actual candidate comparison on the current model. Functional verification scope from screen → main app execution → detailed devices is complete; ROM cold boot, long-duration/precision, and physical certification are excluded. The following records each task's historical state.

bw489 [original sensor task consumption](../hardware/sensors-input/sensor-task-consumption.md): Three originals FIFO32/WM10 → GPIO38/IRQ57 → natural sensor_hub consumption 10; numerical ring 2252/original ARM codec 80 exact; each 100 ms no-input ring preserved; post-input UI 7→12/fault 0. Only existing pulse component reused; gate/ready/caller forcing 0; frozen stdlib audit/nine negatives; seven native runs (one pre-injection query failure + six successes), containers absent. E12 complete, 16/16, but overall Goal awaits final audit.

bw488 [touch and ring input acceptance](../research/input-acceptance.md): Three originals' ring → actual UI return/576×288/subsequent 100 ms frames 3→7; virtual one-second no-input UI 0/initial CPU, SRAM, model exact. Existing three touch scroll/control cases reused; 23-module frozen audit/nine semantic negatives; three partial cases rejected/six containers absent. E11 complete, 15/16=93.75%; E12 and overall final audit remain.

bw487 [three originals' additional touch/UI](../hardware/sensors-input/active-hud-touch-family-contract.md): Stock24 reused/old2 four native runs; each input/no-input 200 ms. Original command handler/cleanup/same TCB → 3790 pixels each, frames 13→18; 40 no-input samples unchanged; starting/ending frames exact across three families; source 6/stack 128 and 120 distinguished; frozen audit/four negatives; six cold SRAM regions exact. Ring remains/E11 partial; 14/16 retained.

bw486 [active HUD touch/UI](../hardware/sensors-input/active-hud-ui-consumer-contract.md): Stock24 original additional input → UI7/display command response 4 → event 3/original handler/cleanup → 3790 pixels changed, five frames. Same 200 ms no-input 40 samples unchanged; same main/model/run; fault 0/frozen audit/five negatives. Two older mains/ring incomplete; E11 partial, 14/16=87.5% retained.

bw484 [active-board reset acceptance](../hardware/power/active-board-reset-acceptance.md): Three originals E05 active screen → virtual NVIC reset → original vector/service → new UI/5 frames/task wait resumed; reset 0→1→1, GPU 7→0→7, cache/IMU/peer/UART initialized, ITCM/NOR/FS preserved, fault 0. Existing guards/cache fix reused; measured XOR100/IOM7 shared-gate profile; 13 frozen dependencies/3 semantic negatives; 5 containers absent. E06/M3 complete, 14/16=87.5%, E11/E12 remain.


bw483 [original main boot acceptance](../firmware/native-main-boot-acceptance.md): Directly paired verification of three originals' reset/service return/initial UI → actual empty UI queue receive wait 10 ms after first screen → original callback resume in same TCB (4.755/4.873/4.815 ms). Main/board/model unchanged, six initial SRAM regions exact, 5 frames, fault 0; nine-dependency frozen audit; three semantic negatives/partial-case integration rejected; three containers absent. E05 complete, 13/16=81.25%, E06/E11/E12 remain. Physical hardware/agents/publications 0.


bw482 [three originals' post-screen lifecycle](../bootloader/boot-family-post-screen-lifecycle.md): Stock 2.3 100.107 ms/Faceclaw 100.120 ms, five frames each, serial 3→7, fade-in and sleep entry/exit, fault 0. Originals/device models unchanged; six initial SRAM regions exact. Frozen eight-dependency audit of three families including saved stock24 evidence; two negatives rejected. Four original UI callbacks each and final event-list membership confirmed; direct wait→resume pair deferred to next step. E05 partial, 75% retained.


bw481 [three originals' first screen](../bootloader/boot-family-first-screen.md): Stock 2.3 and Faceclaw original reset → touch/UART → normal UI return → 31 lists/120 draws → completed 576×288 source. Raw SHA matches stock24; six initial SRAM regions exact/guard; fault 0; independent frozen nine-dependency audit/two semantic negatives rejected. Post-first-screen lifecycle for the two families incomplete; E05 partial, 12/16=75% retained.


bw480 [post-first-screen lifecycle](../bootloader/post-screen-boot-lifecycle.md): Reproduced first frame of stock24 pinned model/original → 100.695 ms; five original completed frames, fade-in, zero missing, sleep entry/exit present, fault 0. Schema2 evaluation and independent audit of three semantic negatives/eight frozen dependencies. E10/M6 complete, 12/16=75%. E05 three originals, reset, additional input/sensor consumption, and physical hardware incomplete.

bw479 [first natural dashboard](../hardware/display-gpu/first-native-dashboard-frame.md): Stock24 original reset → touch/UI → 44 glyphs/120 draws → packing → 576×288 dashboard obtained. Main unchanged/three initial SRAM regions exact; faults/rejections 0; completed source/raw and gain-16 view preserved. Explicit functional models for cold sensor/reference GPU; physical hardware, full boot, and continuous frames incomplete. E09 complete, 11/16=68.75%. Next: post-first-screen boot lifecycle.

bw478 [SDK 2.0.0 actual source review](../research/icm45608-sdk-source-review.md): Preserved user ZIP, extracted 368 text files, reviewed GAF examples. 45 of 46 sensor drivers match existing public blobs after LF normalization; only version rc1→2.0.0 changed in the other. Official GAF example cold input/output and ICT1531x source added to evidence, not a new implementation of full GAF calculation. Separate functional model design recommended; implementation/new ARM/physical hardware 0; 62.5% retained. Browser Skills Chrome connection confirmed.

bw476 [normal GAF execution material dependencies](../hardware/sensors-input/gaf-family-guide-and-access-evidence.md): Newly downloaded public official AN-000478 rev1/54 pages; reviewed target differences, text, and rendering. Target ICM45608 SDK still requires login. GAF requests 2/4 calculation, ISA, and independent results unavailable. Model changes/new ARM/physical hardware 0. Recorded common gaps and resumption inputs for six remaining conditions; stopped repeating the same diagnostics; overall 10/16=62.5% retained.

bw475 [FIFO → pulse → GPIO38/IRQ57](../hardware/sensors-input/imu-fifo-gpio-irq-integration.md): Verified original INT1 low3=1 push-pull/active-high/pulse, correcting initial latch assumption. Original setter/WM10 → GPIO38 → original ISR/callback/exception return → separate original consumer 10 packets; 2252-byte ring exact to existing formula. 36 checks including 8/100 µs pulses; optionalWatch on/off six SRAM regions/WORK exact; stored audit 103/12 containers absent. Gate 0; natural task consumption and GAF incomplete; overall 62.5% retained.

bw474 [original FIFO configuration → consumption](../hardware/sensors-input/imu-fifo-native-configuration.md): Connected shared CFG2/ODR, timed IREG, atomic bank. Stock24 original setter R0=0/frame 0→32/WM10 → original consumer 10 packets/320 bytes; 2252-byte ring math exact; Watch on/off initial/post-configuration/final SRAM and WORK exact. Configuration 32, legacy raw 70/228, transport 176, ODR 1278, threshold 27, saved-input audit 109/21 containers absent. Synthetic API diagnostic; natural GAF/GPIO/root full return incomplete; overall 62.5% retained.

bw473 [raw32 parser → M55 consumption](../hardware/sensors-input/imu-fifo32-parser-and-transport.md): Three originals parser/callback 120 + codec 3 isolated; ES valid/offset/size 6, 9 and endianness confirmed. Raw32/cap64 model; final 70/legacy 228, 176, 27. Stock24 M55 WM10/320 bytes → callback/ARM decoder 10 times; 2252-byte ring math exact; Watch control SRAM/WORK exact; codec output 80 bytes cross-exact; audit 65/eight containers absent. Host frame configuration/guest configuration/GPIO/GAF incomplete; 62.5% retained.


bw472 [actual FIFO configuration discovery](../hardware/sensors-input/imu-fifo-guest-configuration-contract.md): Confirmed three originals' enable branch requests ES0/ES1, 32 bytes, WM10/stop-on-full and setter frame 32. Setter 908 bytes identical; isolated ARM 186 (ABI stub)/audit 37; new M55 0. Next: raw32/ES callback contract → shared CFG2/timed IREG/original configuration → IRQ. Raw16 is a separate experimental profile; GAF incomplete; 62.5% retained.


bw471 [FIFO threshold → upper-layer consumption](../hardware/sensors-input/imu-fifo-threshold-status.md): Default off; successful-enqueue-based latch/generation/R-C transactions and logical IRQ. Actual IOM final 27/legacy 176/raw 228; original stock24 upper status → count 2 → data → parser/callback, two samples/four transactions, source-owned ring exact; Watch on/off SRAM/WORK exact. Audit 68/12 containers absent; resetdone 1-byte collision failure preserved. Guest configuration/GPIO/GAF and full root return incomplete; 62.5% retained.


bw470 [original RTOS FIFO transport](../hardware/sensors-input/imu-platform-fifo-m55.md): Full-board original Sensor Thread/PSP FIFO API → mutex acquire/IOM preparation/HAL/cleanup/release → parser/callback, two samples stored. Gate 0/IRQ mask unchanged; actual count 2/data 32; 2252-byte ring exact; Watch on/off final SRAM/WORK exact; audit 61/four containers absent. Incorrect-copy failure preserved; natural IRQ/status/GAF incomplete; 62.5% retained.


bw469 [original M55 HAL → FIFO → parser](../hardware/sensors-input/imu-hal-fifo-m55.md): Stock 2.4 isolated synthetic caller returned normally in six original HAL calls and seven including parser; actual IOM six commands/three transactions/two packets consumed; 2252-byte ring raw/float/time exact; other SRAM control exact; audit 29/six containers absent. Natural main/RTOS upper layer/GAF incomplete; 62.5% retained.


bw468 [FIFO I²C adapter](../hardware/sensors-input/imu-fifo-i2c-transport.md): Actual IOM length/4-byte splitting/Finish → FIFO consumption; 176 checks per endianness; 2 KB/backpressure/reset/CONT/queued-flush guards. Final stock24 cold off/on SRAM baseline exact/FIFO transactions 0 (three new mains total/two final); audit 41/11 containers absent. Original sample consumption/flush and IRQ integration/GAF incomplete; 62.5% retained.

bw467 [raw FIFO storage/consumption](../hardware/sensors-input/imu-raw-fifo-storage.md): Default-off C# component; raw16/2 KB packet queue; count/full lease/defensive copy/flush/reset implemented; 228 Renode checks. ID peer/IOM/GPIO unconnected; partial abort unsupported; new original ARM 0; GAF/natural consumption incomplete; 62.5% retained. Next: optional bus connection.

bw466 [sensor role dependency](../hardware/sensors-input/sensor-role-initialization-dependency.md): Three current originals are already Master low/role 1/mode 3. Mode 3 zero-period helper returns -1/SRAM unchanged/GAF flag 1 preserved; wrapper continues into initializer. RAM type 1/2 dispatch confirmed; 27 isolated ARM; existing NAK/ID reruns 0. Not a replacement for normal GAF; next peer FIFO device lifecycle; 62.5% retained.

bw465 [GPIO38 actual IRQ57](../hardware/sensors-input/imu-gpio38-runtime-ingress.md): Added default-off input; device 42/existing BLE 26/touch 42. Three originals reset → edge → ISR/callback IPSR73 → clear → original getter/CPU return; prefix/injection exact; gate 0 retained. No-input/off controls' final SRAM/CPU/time exact; audit 67/nine containers absent. Normal GAF/FIFO consumption/screen incomplete; 62.5% retained.

bw464 [IMU gate/GPIO38](../hardware/sensors-input/imu-fifo-gate-and-pin-contract.md): Gate is initialization wrapper return flag, not IRQ pending; 1 even on error return. Three originals mode/gate/timestamp 63 isolated conditions; host gate writes 0. Pin 38 flash/SRAM registration and bank 1 IRQ57 vector/context confirmed; edge/enable/actual IRQ unverified. GAF/natural consumption incomplete; 62.5% retained.

bw463 [FIFO read transport](../hardware/sensors-input/imu-fifo-read-transport-contract.md): Original upper function status → count 2 → data → parser/sample in 24 isolated runs; driver errors 24/zero gate 3 = 51. I²C ABI responses/original output initialization, second count use, continued reading after errors/-3 confirmed. Bus/IRQ/natural M55/GAF incomplete; 62.5% retained. Next: original gate/timestamp producer.

bw462 [original FIFO parser](../hardware/sensors-input/imu-fifo-parser-contract.md): Verified bytes → actual frame parser → previously registered callback → sample ring across three originals. Two endiannesses/four axes/five counts = 120 + three observer-off; 123 final runs; invalid sensors excluded/time, wrap, full SRAM checked. Four initial temperature-bit expectation error attempts preserved; bus/IRQ/natural main/GAF incomplete; 62.5% retained.

bw461 [raw IMU event consumption](../hardware/sensors-input/imu-raw-event-consumer-contract.md): Three originals' callbacks: four axis types × four masks × two indices = 96 runs + six observer controls. Raw/float conversion, time/20-slot wrap, full SRAM preservation confirmed; stubs 0. Synthetic events/isolated M7; FIFO/IRQ/natural main incomplete; models 0; 62.5% retained. Next: original FIFO caller/bus contract.

bw460 [original ARM correction comparison](../hardware/sensors-input/gaf-original-arm-correction-comparison.md): New 45687/G2 memmap differences; three originals' six signed-trim types/three legacy controls, 21 final runs; 48 existing records checked. No writes to four areas corresponding to new correction; non-trim transactions identical; 14 extra initial control-input error attempts preserved. Cannot replace normal GAF; models 0; 62.5% retained.

bw459 [GAF host correction evidence](../hardware/sensors-input/gaf-host-correction-evidence.md): Newly available official ICM45687 source confirms negative clock correction formula, but a function after requests 2/4 cannot replace full EDMP calculation. Pinned commit/four blobs, sequence and ten checks; model/ARM 0; 62.5% retained. Next: compare existing derived values and corresponding ranges in G2 original setter.

bw458 [public Ring scenario](../hardware/communication/ring-public-scenario.md): Independent 62-file/63 MB workspace; three originals/registered candidate CLI passed; actual ARM source 4→5 regression detected exit 1 despite UI entry. Five new native/five saved audits (zero additional VMs)/10 CLI/45 aggregate; zero old-asset reads; bw457 six SRAM regions exact. UI return/pixels/GAF incomplete; 10/16=62.5% retained.

bw457 [Ring → app/UI wake](../hardware/communication/ring-app-wake-contract.md): Stock 2.4 actual 108/ACK → original app role 255→4/tick 5288 → app 1 request/single reply → ui_task callback entry. IOM7 XOR100 boundary identified; existing shared IOM profile reused; five SRAM prefixes exact; audit 45. UI return/pixels/GAF incomplete; 10/16=62.5% retained.

bw456 [three originals' ring and duplicate suppression](../hardware/communication/ring-family-and-duplicate-contract.md): Two new old2 native runs/stock24 reused; original relay/queue/ring and CFW actual fallback confirmed; audit 60. Stock24 two reports/60 bytes → two receivers/one slider, tick 1000 retained; audit 27. New models 0; UI/screen incomplete; 10/16=62.5% retained.

bw455 [original Ring relay ingress](../hardware/communication/ring-input-ingress-contract.md): Stock 2.4 UART0 30 bytes/exception 31 → original ring task → source 4/code 1 → caller return; audit 23. Three originals isolated M7 57 scenarios/190 checks; source 27. Harness API/IRQ index errors preserved; UI/other-original native/direct R1 BLE unverified; 10/16=62.5% retained.

bw454 [three originals' repeated input](../hardware/sensors-input/touch-repeat-family-contract.md): Two new old2 native runs/stock24 reused; same model; two separate reports → original handler/slider/caller return; audit 72. CPU/SRAM/time preserved; second UI/ring/pixels incomplete; E11 partial; 10/16=62.5% retained. Next: common input scenario integration.

bw453 [repeated touch lifecycle](../hardware/sensors-input/touch-repeat-frame-lifecycle.md): Default-off reload adapter; synthetic 86/existing 59 values identical; stock 2.4 two GPIOs → separate reports → original slider/caller return; audit 30. CPU/SRAM/time preserved; physical hardware/second UI/pixels unverified; E11 partial; 10/16=62.5% retained. Next: old2 repeated-input controls.

bw452 [three originals' touch wake](../hardware/sensors-input/touch-wake-family-contract.md): Stock 2.3/Faceclaw also confirmed GPIO27 → original UART request/single reply → app1 callback entry. CFW actual-condition hook/fallback; external 16-byte frame; same model for both families. Return/pixels/gesture/ring incomplete; original 2.4 reused; 10/16=62.5% retained.

bw451 [official GAF evaluation distribution](../hardware/sensors-input/gaf-public-evaluation-package.md): Obtained newly public SensorStage ICM45608 2.0.0 archive/LFS pin; indexed 68 GAF/on-demand fields; pinned memmap 64 addresses/widths match. 31 material checks; ARM 0/model changes 0. Normal GAF ROM/ISA/numerical oracle unavailable; general ready unimplemented; 10/16=62.5% retained.

bw450 [GAF and render scheduling](../hardware/sensors-input/gaf-render-scheduler-dependency.md): Existing frozen-core fault profile request 2/trigger, busy 178, guard 0. Renderer ready/notification 1, but sensor 41 > draw 40; original selector (isolated M7) also selects sensor. Four prefixes exact; audit 23/selector reruns 2. Normal GAF/pixels incomplete; next execution/return contract; 10/16=62.5% retained.

bw449 [post-UI broadcast completion](../hardware/display-gpu/ui-post-callback-broadcast.md): All ten eligible callbacks called and returned; original UI return confirmed. Separate recipe excluding three high-frequency observations; audit 59. Then sensor_hub GAF request 2/IOM4 strict boundary; draw 0. Next existing GAF fault profile/scheduling dependency; 10/16=62.5% retained.

bw448 [natural UI initialization return](../hardware/display-gpu/ui-layout-initialization-frontier.md): Tree 54 nodes/depth 10, no cycles; actual update return confirmed. Original app initialization/UI callback return in source HP167 interval; transition SRAM/CPU/time preserved, prefix exact. No draw entry for 100 ms after callback; next refresh delivery conditions; 10/16=62.5% retained.

bw447 [natural UI font lookup](../hardware/display-gpu/ui-initialization-font-progress.md): Original ui_task descriptor 888 entries/887 returns, 33 characters; five frames based on source size confirmed. Same model/board; initialization return/Ambiq not reached; pixels unverified. Next trace layout termination condition/repetition cause; 10/16=62.5% retained.

bw431 [runtime CLI dependency isolation](runtime-cli-import-isolation.md): Removed unnecessary parser eager imports to separate help/decode. Three blocking tests/three frozen; saved stock 25/candidate 28 byte-exact; device model changes 0. Next connect existing runner+compare in one command; overall 8/16=50% retained.

bw430 [request 4 and preceding WDT](../hardware/sensors-input/gaf-after-first-timeout.md): After the first stock 2.4 timeout, original request 4 → watchdog request on the second 66808th poll preceded cleanup. First core/four SRAM regions exact; audit 26/three counterexamples; no actual reset. Stopped expanding frozen variants; next E16 common tools/normal calculation evidence; overall 8/16=50% retained.

bw429 [original first GAF timeout](../hardware/sensors-input/gaf-timeout-cadence.md): Stock 2.4 completed original 200000 polls → actual wait/helper/setter return R0−4 under the interval HP profile. WDT active, guard fault 0, transition state/prefix exact; audit 24/three counterexamples. Normal calculation and subsequent initialization incomplete; 8/16=50% retained.

bw428 [HAL-derived timing profile](../hardware/cpu-memory/hal-loop-time-profile.md): Verified original HAL and independent STIMER/WDT time under separate LP64/HP167 profiles. Identified cause of HP time 1 µs quantization; initial failure preserved/same tolerance; execution exact. Not adopted on default board/RTOS; audit 31/three counterexamples; 8/16=50% retained. Next check mode after ATT, then interval diagnostic.

bw427 [GAF delay and virtual time](../hardware/sensors-input/gaf-delay-clock-contract.md): Confirmed minimum 811 instructions for original 5 µs request take 81.1 µs at current 10 MIPS. Distinguishes HAL's 3 cycles/loop contract from virtual MIPS. Four SRAM regions/existing results exact; audit 22/three counterexamples; CPU/WDT/timeout unchanged. Next independent verification of separate timing profile; overall 8/16=50% retained.


bw426 [app return after watchdog](../hardware/power/watchdog-reset-restart.md): Stock 2.4 natural WDT reset → retention → new service/connection/ATT/RTC commit 1 succeeded. Corrected completion wait using actual Pause deadlock trace; four SRAM regions exact; audit 22/three counterexamples. Normal GAF/required initialization incomplete; overall 8/16=50% retained. Next return to E05 calculation/failure-return evidence.

bw425 [watchdog actual virtual reset](../hardware/power/watchdog-reset-delivery.md): Confirmed stock 2.4 original natural request → original vector/SP re-entry. Independent gate/lifecycle 38; audit 15/three counterexamples; PC seed 0. Original STAT consumption/app return unverified; next connect guarded cause read/retention lifecycle. Overall 8/16=50% retained.

bw424 [watchdog reset contract](../hardware/power/watchdog-natural-request-contract.md): Confirmed original CFG, restart 188, and gate permission. Current model pauses before reset; nominal 14 seconds under LFRC assumption is not measured time. Next connect verified reset profile and explicit main-only cause delivery. Audit 20/three counterexamples/frozen exact; overall 8/16=50% retained.
At this checkpoint acceptance was **10/16=62.5%**. The bw figures below are historical; current status follows the dashboard and scope v3.

bw423 [version query and watchdog boundary](runtime-local-version-query.md): Original consumed virtual 0x1001 response and ran 12.005 more seconds after ATT. A longer run was stopped at 13.246 seconds by the watchdog reset-request callback. GAF timeout did not arrive first; next is watchdog gate/reset and clock contract. Actual reset and normal GAF calculation unverified.

bw422 [controller dependency of GAF timeout](../hardware/sensors-input/gaf-natural-timeout-controller-frontier.md): Retaining original wait limit, ran virtual 9.746 seconds/11,059 busy after ATT, but stopped strictly before ble_wsf's 0x1001 version query. Timeout return unverified; next is exact virtual controller response contract. The bw421 read-mediated candidate was not adopted for lack of evidence of effect.

bw420 [reset domain audit](../hardware/power/reset-domain-acceptance-audit.md): Fixed cache activation/initialization history incorrectly persisting after CPU reset. Separates narrow device reset/app reprocessing evidence from E05 required initialization dependency. E06 partial; next E05 GAF/legitimate initialization path.

bw419 [post-reset memory protection](../hardware/power/reset-memory-protection-lifecycle.md): Fixed an issue where page I/O routing was cleared, allowing padding reads. Passed 24 synthetic/three original regressions and preserved historical failure artifacts.

bw418 [three originals' reset reprocessing](../hardware/power/reset-restart-version-profiles.md): Stock 2.3/Faceclaw also succeeded in reset → service → new virtual connection/ATT → RTC commit 1 under the same shared model. Stock24 reused existing artifacts; two new native runs/audits 30, 31, 31. E06 partial until independent post-reset protection/lifecycle verification; 8/16=50.0% retained.

bw417 [post-reset app reprocessing](../hardware/cpu-memory/cpu-retention-preparation.md): Stock 2.4 original reset → RET/WFI → service reinitialization → new connection/ATT → RTC commit 1 succeeded. Renode sleep 21.2058 ms/IRQ32 prefix confirmed; event overflow and unverified physical timing/full boot preserved. E06 partial pending other originals/lifecycle audit; 8/16=50.0% retained.

bw416 [CPU retention setup](../hardware/cpu-memory/cpu-retention-staging-contract.md): Analyzed 0x22 configuration in three originals and confirmed natural return of the stock 2.4 post-reset setup function. Only optional register storage implemented; subsequent deep-sleep preparation, entry/wake, and app return incomplete. Overall 8/16=50.0% retained.

bw415 [system reset during original execution](../firmware/original-main-system-reset.md): Confirmed stock 2.4 actual ATT processing → NVIC input → original vector/SP re-entry and 20 ms initialization. Subsequent CPDLPSTATE 0x22 causes strict stop; E06 partial, 8/16=50.0% retained. SRAM 204-byte difference/RTC epoch return are separate state-lifecycle boundaries.

bw414 [system reset foundational contract](../research/system-reset-boundary-contract.md): Reproduced pinned engine BASEPRI cache persistence on synthetic M55 and confirmed IRQ resumption with a separate opt-in model. Original G2 app post-reset return unverified; E06 partial, 8/16=50.0% retained. Next: declare RAM/NOR/RTC/ITCM reset domains and integrate original board.

bw413 [E14 acceptance audit complete](../research/peer-failure-acceptance.md): Reverified nine pinned scenarios of disconnect, bad CRC, delay/actual timeout/reconnect across three originals, reaching **8/16=50.0%**. Additional ARM 0; denominator/acceptance wording retained; normal GAF/integrated screen/API 3 of 6 remain incomplete. Next proceed with remaining eight conditions' reset lifecycle, natural service/screen, and development flow. Figures below are checkpoint history.

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

bw378 latest integration: Connected previously verified IMU component/fixture to the device communication runner using the [runtime GAF profile](runtime-gaf-profile-integration.md). Confirmed three originals' time/close regressions and GAF 153 read/225 write. Next common boundary is first GAF service 7c000402 at approximately 171 ms; calculation/normal initialization and long timeout incomplete. Overall 5/16=31.25% (displayed 31.2%) retained.

bw377 latest dependency: Verified three originals' immediate release/CRC rejection and 1 ms delayed input in the [peer communication failure contract](runtime-peer-failure-contract.md). The 1000 ms case first reached the legacy runtime IMU/IOM4 boundary. Integrate existing verified GAF component/board fixture into runtime, then return to actual normal service effects and long communication failures. E14 partial and overall 5/16 retained.

Latest bw375: [Device ATT → original RTC time setting](runtime-att-time-device-ingress.md) completed E13. Overall 5/16=31.25% (displayed 31.2%); API screen 3/6 is separate. Next pin original termination/recovery contracts for E14 disconnect, delay, and malformed messages in the same runner. Natural GAF, full screen, and outbound peer delivery incomplete. Figures below are historical checkpoint values.

The active goal is the 16 acceptance conditions in [scope v3](../data/project-scope.json). At this checkpoint overall progress was 10/16=62.5%, and the first-screen checklist including API diagnostics was 3/6. Overall completion requires actual evidence for all 16.

The normal baseline natural main in bw353 read explicit trim 0x85 and stored 225 bytes bias/GAF before reaching the first GAF service request. Follow [current boundary and reproduction](../hardware/sensors-input/imu-clock-variation-contract.md). The old IMU 02ae boundary is preserved as an option-off control. The bw358 initial readiness/ID failure experiment also reached first GAF service but is a separate failure profile and does not replace the normal baseline. It is separate evidence from API diagnostics/GPU path. Current task sequence and scope reassessment follow the [bw365 review](emulator-scope-audit-bw365.md).

## Product to develop

When a user selects supported original/new CFW and a scenario, execute the actual ARM main on a virtual G2. Obtain firmware behavior in response to virtual device inputs, time, sensors, and peer messages, as well as screen, memory/communication differences, and failure causes. An app feature reimplemented as a host model is not reported as original execution.

The first supported unit is one temple main and an explicitly defined virtual peer. Scenarios needing the opposite temple/case declare its role/version/responses and disconnects. Full execution of both CPUs/case firmware and complete ROM/bootloader/OTA flow are separate profiles. Unsupported profiles are not made to succeed automatically.

## Pinned acceptance conditions and score rules

| Area | ID | Behavior to complete |
| --- | --- | --- |
| Execution foundation | E01–E04 | Pinned inputs/tamper rejection, M55 reset reproduction, exception/protection basics, new CFW registration |
| Execution lifecycle | E05–E08 | Service/app events, reset, persistent data preservation, storage failure/interruption/mismatch |
| User behavior | E09–E12 | Natural 576×288 UI, continuous frames, device input, sensor sample consumption |
| Test tools | E13–E16 | Virtual peer app messages, peer errors/reconnection, stock/CFW comparison, one-command execution/reporting |

Specific acceptance for each item is in scope JSON; all 16 carry equal weight. Full verification of one item adds 6.25 percentage points. Partial scores, test counts, and file counts do not contribute to the overall score. At this checkpoint 8/16 was 50.0%. When new requirements are discovered, record the scope version and before/after criteria.

## First vertical path to complete

The six stages from “original main reset to first screen” were pinned in advance at this checkpoint.

1. **Complete:** Run three originals from reset; pin current context, waiting tasks, and input sources.
2. **Complete:** Establish original UI API input → display activation producer causality. This reaches the API boundary; phone/GATT remains in E13.
3. **Partial:** Original activation preparation and mode 1 executed. Frame type 3 preparation/refresh is not yet connected.
4. **Complete:** Confirm original UI/display resumption in API diagnostics and actual `ambiqdraw` task draw/target setup calls. Later bw346 also confirmed actual submission and guest surface, but full UI/frame wrapper and natural main remain incomplete.
5. Original render/submission generates and captures a full guest frame.
6. Reproduce first screen from reset under the same profile; compare pixels and failures.

This six-stage percentage is separate from the overall 16 conditions. At this checkpoint it was 3/6=50.0%, not added to the overall score. Even if a stage passes, the condition's full 6.25 percentage points are not awarded until all of E09 is complete. Forced PC/return/mode/TCB changes are not used as integration success to make the goal easier.

After the screen, complete first input or phone message → original consumption → screen change. [New CFW registration (E04)](../firmware/firmware-candidate-registration.md) is complete; comparing registered candidate behavior in the same scenario (E15) remains. Storage/reset/failure and sensor/peer errors remain in the denominator, so the first screen alone does not complete the project.

## Rules for selecting next work

Do not add a standalone tool merely because another unsupported register was discovered. Connect it to current acceptance conditions and dependencies; extend existing models, runners, and scenarios where possible. Perform source analysis when it resolves an unknown or enables an integration experiment.

Before each task, record required acceptance dependencies and continue/hold/switch decisions for each outcome. If two consecutive tasks do not change the goal's causal chain or a required dependency, switch paths before a third similar probe. Do not continue solely because one new register fact was found. Investigate the unknown IMU 153 bytes together with actual consumption, preservation, and necessity; do not fill them with arbitrary zeros. Do not yet assume IMU completion causes automatic UI start.

Current API diagnostics first follow [GPU runtime wake and command packet](../hardware/display-gpu/gpu-runtime-wake-and-command-packet.md). Initial activation evidence is preserved in [original UI/display activation](../hardware/display-gpu/display-activation-native-diagnostic.md). Current support and commands follow the [catalog](emulator-capability-catalog.md), review evidence [Astra review incorporation](emulator-scope-review.md), and overall status the [dashboard](../project-dashboard.md). This roadmap does not grant physical device access/write authorization.


## Minimum verification scenarios for remaining acceptance conditions

This implementation plan was organized in the bw343 review. It does not replace or reduce existing E04–E16 acceptance. Pin specific values, message IDs, and time budgets for inputs below with source evidence before each task, and do not declare completion while unresolved. Default targets are the same one-temple profile for stock24/stock23/Faceclaw38; E04/E15/E16 also include a new candidate.

| Condition | Minimum normal scenario and expected result | Failure controls and unresolved boundaries |
| --- | --- | --- |
| E04 candidate registration | Register new candidate SHA, vector, layout, compatibility declaration; run same runner | Reject size/vector/profile mismatch. Merely changing the current three-image allowlist is not a substitute |
| E05 service/app | Main reset → required initialization → original task processing of supported app events | Detect unsupported access/errors. Exclude forced branch or TCB/return changes. Current API insertion diagnostic is partial evidence |
| E06 reset | Virtual device reset during execution → check volatile/retained state → app re-entry | Detect incorrectly retained volatile state and reinitialization failure. Reset cause/retained areas must be pinned |
| E07 storage | Original virtual storage write → restart → consume same data | Three originals' kvTime/NOR restart reads complete. Verify neighbors/input preserved; subsequent full boot is separate |
| E08 storage failure | Restart after write/erase failure, interrupted write, or data/version mismatch | Assess corruption extent and recovery/explicit failure. Do not overwrite with success responses |
| E09 first screen | Legitimate initialization/input without test caller → original UI/draw/submit → 576×288 guest frame/viewer | No-input/invalid-input controls and pixel provenance. Distinguish current API diagnostic guest surface and synthetic 64×32 |
| E10 refresh | Sequence and pixel changes of continuous frames under pinned virtual time/events | Detect submit without completion/frozen frames. Pin events, frame count, and time budget |
| E11 input | Deliver v1 touch via bus/GPIO/IRQ → original consumption → state/UI change | No-input and invalid/duplicate input controls. Gesture/ring support list unresolved; do not automatically reduce scope to touch |
| E12 sensor | IMU sample → FIFO/IRQ → original consumption result | Empty FIFO/IRQ clear and unsupported access controls. Pin required auxiliary sensors and sample format |
| E13 peer communication | Declare phone/opposite temple/case roles → transport message → original task/app behavior | Detect wrong target/unsupported message. App message ID/payload and each peer role require source confirmation |
| E14 connection failure | Inject disconnect, delay, and malformed message separately → timeout/error/state → reconnect or explicit failure | No unconditional ready/ack. Pin delay, message mutation, and expected reconnect state |
| E15 comparison | Run stock/new candidate with same model/input/virtual time → assess differences and preserved behavior | Separate fixture differences from firmware regressions. Declare intended changes/preservation contract in advance |
| E16 development tools | One command runs registered candidate/scenario → frame/events/failures/comparison report and reproduction | Check new environment, missing assets, and interrupted process cleanup. Distinguish a simple bundle of diagnostic scripts |

The next sequence is (1) establish diagnostic causality for valid content after activation → original app dispatch → first draw/submit, (2) reproduce natural execution from reset through full screen and subsequent screen via device/transport input, and (3) integrate registered new candidate → same scenario → comparison report. Judge each relevant E condition separately at each stage. Storage/reset/sensor/peer failures remain in the overall 16 conditions.

## Staged history — “current” and “next” below refer to each checkpoint

The latest natural main at this checkpoint stopped at the unsupported first GAF service after bw353 explicit trim and 225-byte storage. Current priorities, next judgment, and conditions for an overall score increase follow the [latest scope audit](emulator-scope-audit-bw365.md). Reuse existing evidence rather than restarting the next tasks in the checkpoints below.

The first bw344 diagnostic unit confirmed app dispatch/callback causality. One byte received by MSPI0 command 05 before the first submission is the next dependency. First investigate the consumption contract in [execution and stop evidence](../hardware/display-gpu/ui-content-render-ingress.md); do not bypass with an arbitrary response.

Later bw345 implemented JBD status transactions and failure controls, confirming actual `ambiqdraw` entry (M4) across three originals. Next connect GPU power/LDO runtime wake through list production and submission. Status response is an explicit virtual profile, not natural main/pixel completion. [Evidence and reproduction](../hardware/display-gpu/jbd-display-status-and-render-task.md).

bw346 connected runtime wake, Nema initialization, and original packet production. Next: GPU model consuming actual commands, framebuffer, and completion IRQ. Follow [reproduction and incomplete boundaries](../hardware/display-gpu/gpu-runtime-wake-and-command-packet.md). 3/16 and checklist 3/6 retained.

The one-time bw347 Astra review retained that scope. The next GPU diagnostic unit is actual packet/list semantics → supported command consumption → guest framebuffer change → completion ID/IRQ → original waiter resumption. Verify invalid command/DMA range and incomplete controls together. Do not assume the first 24 words generate a full screen; identify necessary subsequent original submissions. Once diagnostics are connected, return to natural main IMU 02ae/153-byte boundary and the broken device/transport input → UI producer path before further GPU expansion. Causality between them remains unproven; GPU diagnostic success does not replace E05/E09 completion.

At the bw346 first-clear checkpoint, first GPU list consumption, clear, completion IRQ, and original second submission were confirmed. The subsequent 108-word shape stream is the boundary. M5 partial; not full frame/UI or natural main completion. Next connect rectangle/line and clip state streams in the existing consumer, verify nonzero UI/full frame, then return to natural IMU/device input paths. Reuse initial wake and JBD verification.

bw346 shape-stream checkpoint: Confirmed three originals' actual 11 lists/106 draws, 11 IRQ assert/ack, and nine white pixels at 576×288. The next 252-word vertex/curve coverage is the boundary; full frame wrapper/natural main incomplete. First follow [shape-stream evidence](../hardware/display-gpu/gpu-native-shape-stream.md). M5 partial, overall 3/16, auxiliary 3/6 retained.

Latest bw346 [quad coverage](../hardware/display-gpu/gpu-quad-coverage-contract.md): Confirmed three reference native runs, 14 lists/142 draws, completion 12/ID3, and one strict control. The current 102-word suspected display-buffer conversion path is the next unit. Confirm inputs distinguishing alternating nibble/matrix offset/quantization and the original shader contract before proceeding to full frame/natural main. Physical MSAA/full frame incomplete; denominator/score unchanged.


## bw348 workflow reassessment and GPU stopping boundary

The user-requested one-time Astra read-only review retained scope v3, 16 acceptance conditions, then-current 3/16, and API checklist 3/6. The active Goal already has the same emulator scope, so do not replace or recreate it. The review itself is not new feature completion or a score increase.

The current 102-word list was actually submitted next by original execution, providing grounds for continued analysis. Do not expand this into implementing the full fragment ISA or GPU. The stopping condition jointly assesses source, sample positions, nibble/quantization contract of supported two-pass conversion; distinguishing inputs and failure controls; actual guest display buffer; original completion/wait resumption; and whether frame wrapper is reached. If evidence is insufficient, retain unknown and next needed evidence and pause; do not pass execution with a guessed packing formula.

Once diagnostics connect to the original frame wrapper, investigate natural main IMU 02ae/153 bytes and device/transport input → UI producer connection before expanding GPU support. Reaching the wrapper alone does not complete E05/E09 or M6. The natural execution baseline remains at the IMU boundary.

M5/E09 assessment must specify selected GPU profile, supported commands/formats, reference coverage/quantization rules, unsupported boundaries, and failure controls. `area-reference` is a mathematical reference for functional verification, not evidence of bit agreement with physical MSAA. Report both default strict quad rejection and opt-in profile success. With no full UI/natural main evidence at this checkpoint, register neither profile as E09 completion evidence. Do not lower existing acceptance or add new scores.

Pin specific inputs, messages, and time budgets for E11–E14 and other full-scope requirements before starting each task. The current 16 conditions are the functional-scope denominator, not a claim that all device behavior or remaining effort is settled. If detailed conditions change existing scope, record the reason and version.

Later bw346 [packing producer](../hardware/display-gpu/gpu-packing-producer-contract.md): 102 words from three originals' complete conversion functions exactly matched native lists. Confirmed TEX2 AL44 destination and second FORCE_A|ADD; sampling/nibble/quantization are next to verify. GPU model/natural main/overall score unchanged.

## bw364 RX device boundary checkpoint

[Original receive task integration](../hardware/communication/uart0-rx-device-ingress.md) verified three originals' 24-byte error pair, IRQ/ISR, original parser, and return point. displaydrv_mgr_task awakened by a normal reply stops strictly at MSPI0 40060000. Next connect required contract for this original display initialization; request initiation still uses an API caller. Natural GAF barrier, full peer/UI, and short-frame timeout remain incomplete.

[bw366 normal RX → MSPI0 → UI](../hardware/communication/uart-rx-display-mspi0-integration.md): Existing pinned state component/5a01 verified three originals' receive return point, UI delivery, and pending clearance, plus same-model CRC error control. Root request production, short timeout, natural main/full screen incomplete. 9001 recovery preserved at GPU power 40020080 strict boundary.

[bw367 original request producer](../hardware/display-gpu/display-request-root-contract.md): Verified serialized TPL input → registered callback → SendDataToBoth → actual transmit queue in 53 isolated cases across three originals. Distinguished Faceclaw EUS hook/fallback/F0 differences using original ARM. UART task/ID production, BLE device input, service app/display, and natural main incomplete.

[bw368 original task request and DMA production](tpl-native-request-production.md): Verified across three originals that original UART task produces ID/frame from TPL input and caller returns on original stack. Device model/main unchanged; manual node/start/chunk/finish removed. EUS/ATT/controller, app service/display, and natural main incomplete.

[bw369 EUS/ATT integration prerequisites](../hardware/communication/eus-att-device-ingress-contract.md): Verified three originals' ATT groups/permissions/dispatch and DM lookup in 41 scenarios. Snapshot has no active connection, so ATT dispatcher drops before EUS. Faceclaw's actual registered callback is AN wrapper 7d5924, falling back to original EUS for normal input. Next: controller runtime event → original connection state creation, without forcing host security/active flags.


The overall workflow review at that time follows [bw370 scope and next completion conditions](emulator-scope-audit-bw370.md). E13 first establishes the app terminal contract; TPL data transmission and display requests are not automatically connected. Overall 4/16=25.0% and existing 16 conditions retained.


[bw371 TPL service app contract](tpl-service-app-terminal-contract.md): Verified local ble_msgrx → service 80 time-state update in 15 isolated cases across three originals. Original decoder distinguished field128/field16; complete consumption reaches RTC 40004800 boundary. First compare existing RTC model; natural task/ATT/final response remain incomplete.


[bw372 original BLE task time setting](tpl-time-native-rtc-consumption.md): Verified on three originals' M55 TPL API → original ble_msgrx preemption → RTC commit 1 → consuming caller return. Model source/main unchanged; existing RTC write profile selected. Actual ATT input/natural GAF incomplete; overall 4/16 retained.


[bw373 connection event/GPIO contract](../hardware/communication/hci-connection-complete-ingress-contract.md): In 33 isolated cases across three originals, pinned H4/HCI fields, actual DM callback, and GPIO117/IRQ59/original WSF notification. Next connect existing peer runtime event and GPIO pending/IRQ/clear. CCB creation/device input/native unverified in this research; overall 4/16 retained.


[bw374 runtime device connection](../hardware/communication/em9305-runtime-event-gpio-ingress.md): Connected three originals' M55 GPIO117 IRQ59 → SPI/HCI → ble_wsf → CCB creation without API caller/CPU register seed. Default-off CPU/53 observations/full SRAM exact. Next: ATT app data → time-setting terminal value on the same connection; overall 4/16 retained.


[bw432 runtime one-command comparison](runtime-cli-comparison.md): Connected existing comparison API to common CLI. New registered marker ARM execution passed 28 checks/comparison; saved regression candidate failure exit 1 preserved; pre-run profile/model checks and existing result agreement confirmed. Natural main/full UI/frame and new environment incomplete; 16 conditions/8 of 16=50% retained. Next pin scope for connecting existing screen scenario common results.


[bw433 screen diagnostic registered candidate](../hardware/display-gpu/display-runtime-candidate.md): Ran stock/registered marker under same current model on M55 and verified full four SRAM regions/partial surface/observations match. Added one stock baseline run due to historical model differences and recorded why. Five tamper rejections; prior three-original saved audits identical. GPU packing 0x20/final wrapper/natural main incomplete; 16 conditions/8 of 16=50% retained. Next pin common screen comparison/result integration and intended-difference expectations.


[bw434 common screen execution and comparison](../hardware/display-gpu/display-cli-comparison.md): Connected actual marker M55 run/saved audit, same-model comparison, and L8 PNG in one command. Stock baseline reruns 0; full hash/semantic judgments separated; six synthetic controls and model rejection verified. Next pin independent expectation and change/preservation conditions for actual ARM draw mutation. Natural GAF/packing/full UI incomplete; 16 conditions/8 of 16=50% retained.


[bw435 actual ARM screen test mutation](../firmware/arm-display-mutation-oracle.md): Stock24 RGB-zero candidate passed actual M55 screen 20/independent oracle; 684 pixels changed/rest of SRAM preserved; same candidate preserved phone input/RTC 28. Two new native/24 isolated ARM/audit 29. Next cover unverified E15 combinations in original-family/new-candidate matrix. Natural GAF/packing/full UI and denominator 16 retained; 8 of 16=50%.


[bw436 E15 acceptance complete](../firmware/firmware-comparison-acceptance.md): Six pinned pairs of three originals/new candidate separately verified intended ARM screen change and input/communication preservation, actual regressions, and model differences. Stock 2.4 reused/eight new native/48 auxiliary ARM/audit 67. Only E15 complete; 16 condition wording/denominator retained; overall 9 of 16=56.25%. Natural GAF/full UI incomplete; API checklist 3/6 retained.


[bw437 interrupted-work cleanup](native-process-recovery.md): Confirmed existing SIGTERM orphan in actual Renode and implemented cleanup using owned journal/label/immutable ID. Six actual interruption controls, host client exit, sealed-record idempotence, and actual ARM candidate regression passed. E06 dependency on E05 retained; next E16 new-environment/missing-asset guidance. Overall 9 of 16=56.25%/16 condition wording unchanged.


[bw438 E16 development tools complete](../project/development-tools-acceptance.md): In a new offline venv and empty private asset root with 498 files, verified six isolated native runs + one direct documented command run/comparison, guest PNG, missing-asset guidance, and existing cleanup evidence. Existing 16 wording/denominator retained; only E16 done, yielding 10/16=62.5%. Existing Mac Docker/LLVM prerequisites; new OS/natural GAF/full UI unverified; API 3/6 retained. Next return to required E05/E09 dependencies.


[bw439 EDMP execution contract](../hardware/sensors-input/gaf-edmp-execution-contract.md) and [bw440 touch frame](../hardware/sensors-input/touch-event-frame-contract.md): Official target sensor datasheet confirmed custom ISA/requests 2 and 4, but calculation code/independent oracle unavailable. Switched to independent E11 and verified proximity/slider interpretation, delivery, and error controls in 153 isolated ARM cases across three originals. Next connect actual IOM5 chunks and task/IRQ; overall 10/16/API 3/6 retained.


[bw441 IOM5 event consumption](../hardware/sensors-input/touch-event-bus-ingress.md): From three originals' M55 reset, actual input task consumed 16 bytes/four chunks, delivered proximity 2 and slider [1,4,10,167], and advanced to subsequent GPIO boundary. Error frame discarded; existing pin136 frontier separately saved/audited, off exact. Normal 3/error 1/off 1; unit 59/41/44; runner 13. Next current runtime GPIO27 IRQ → task/app consumption; E11 partial, overall 10/16/API 3/6 retained.


[bw442 runtime touch IRQ](../hardware/sensors-input/touch-runtime-irq-ingress.md): Verified three originals' GPIO27 falling → IRQ56/registered callback → original input task → IOM5 frame/notification and slider → original caller SP/TCB return. Five scenarios covering original pending clear, error discard, and pinned GAF no-input 1 ms control; two RunFor abort/legacy GAF strict diagnostics preserved. Device 42/BLE 26; cold CPU/full SRAM exact. App/UI, post-read line, and gesture/ring scope incomplete; E11 partial, overall 10/16/API 3/6 retained.
