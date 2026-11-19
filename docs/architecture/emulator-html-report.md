# Emulator HTML Report

With user approval, the original firmware runner was connected to the existing dark workbench design. To protect proprietary inputs and execution data, output is generated only in a private Blackwall directory and is not automatically published.

## Running built-in scenarios

```sh
blackwall_python="$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python"
blackwall_output="$HOME/Library/Application Support/Blackwall/my-boot-report-01"
"$blackwall_python" -B tools/blackwall_report.py --scenario normal --output "$blackwall_output"
```

`normal` is boot → main → display for pinned stock 2.4 boot/main; `unknown-boot-marker` is an **expected rejection** for virtual metadata. A passed audit of the latter is not normal boot. Docker, a pinned image, private firmware, and models are required. Existing paths are not overwritten. `--boot-image` and `--main-image` specify files, but must still pass the original runner's length, SHA, and vector restrictions. Arbitrary CFW/other-version execution was not yet provided.

If a run folder already exists, use `--capture <existing-run-folder>` to independently reaudit it, then create a report at a new `--output`. Do not repeat the run. Serve the resulting `report/index.html` and asset folder using a local HTTP server. For example, run `python3 -m http.server 8000 --bind 127.0.0.1 --directory "$blackwall_output/report"`, then open `http://127.0.0.1:8000/`. The 3D viewer uses an external CDN.

## Evidence and limits

The report uses actual saved checkpoint order, UART0 receives with virtual timestamps, untimed transmission, verification conditions, and final framebuffer from an audited run. It does not invent missing times for boot checkpoints/TX. The slider navigates recorded times and shows the single final screen only from its recorded point onward. Continuous screen recording and reconstruction of intermediate frames were not yet available. The percentage is observed checkpoints out of seven declared, not chip load or actual boot-completion percentage. Physical component positions and causal links to failures are unconfirmed, so specific chips are not labeled failed components in the 3D model. Errors are shown using confirmed stop boundaries and check results. No actual ROM, physical-device, or physical timing accuracy is claimed.

When execution fails, an error report and private error log are retained. A runtime/host failure is not classified as bootloader failure. `Verified` in the report is a judgment about that virtual scenario and audit.

## Verification record (bw-0593)

New normal and unknown-boot-marker runs were performed separately, with independent audits and HTML generation confirmed. Reaudits of saved positive/negative runs were also checked. A nonexistent boot input causing startup failure produced an `Execution failed` report and error log. Chrome opened normal, expected-rejection, and host-failure reports; status and Logs checklists were inspected with no JavaScript errors. Three existing scenario unit tests passed in the project venv. An initial system-Python run had one failure due to a different dependency environment and is distinguished from the venv result. The first new execution failed because Docker was stopped; after starting OrbStack, a new output path completed normally. Existing audits confirmed the runner cleaned up its owned container and duplicate firmware. Failure output was retained for diagnosis.

## Display and timeline improvements (bw-0594)

The actual original frame looked black because initial fade gave it low maximum brightness. `contrast-preview.png` from the same audited run was made the default, with a switch to the original frame. Correction is for display convenience, not guest memory or measured brightness. From zero seconds, the complete observed original boot order appears in a separate column with missing times marked; the timed-observation column includes saved touch, UART RX, UI-dispatch observer, and frame stop. Missing individual boot/TX times are not invented. A waiting state appears before screen capture. CPU/boot selection points to the model's estimated location based on FCC sample AP510BFA; it does not claim that physical device caused a failure. Physical positions in the model and individual devices remain unconfirmed.

Normal/unknown-marker were independently reaudited into new reports; five venv unit tests, Chrome desktop/mobile, original-frame switch, timeline zero, SoC display, remote-tunnel image HTTP 200, and browser operation were checked. Separate source-based research found five actual frames in a different `post-screen-lifecycle-native-02` run, but did not merge them into the current boot run. Continuous frames from the same run and individual initial checkpoint times require a new observer, original-hook impact controls, and a pinned profile, and were unimplemented. Arbitrary CFW profiles and accurate per-chip activity/failure attribution also remained incomplete.

## Actual time-observation profile

When the profile from the separate [boot-time/frame experiment](../bootloader/timed-boot-observation.md) is explicitly selected, the report replays observation times and framebuffer history collected in the same run. Older runs without times continue to open in the previous order-only view. Profile changes do not overwrite default v1.

## Current-time logs and scrolling (bw-0596)

The bottom area was unified into one chronological log. Only records with virtual time at or before the timeline time appear; past/future filters recalculate on scrubbing. Items without individually collected times in the original execution are not arbitrarily placed on the timeline. Log updates scroll to the bottom. The Logs tab also updates to current time. An actual saved run was independently reaudited; Chrome checks at desktop 1440×900 and mobile 390×844 covered filters at zero/six seconds/end, bottom scrolling, and time changes while Logs was open.

## Boot stages and SoC observations (bw-0597)

An observed-stage list was added beside the board for reset, initialization entry, boot/main transition, input, UART, UI, and frame. The timeline distinguishes observed, recently observed, scheduled, and unobserved; the list scrolls to the relevant item when stage changes. Unknown marker is shown as an expected stop at the specified boundary, not attributed to a particular physical chip. Each stage is an entry observation, not proof of completed device initialization. The SoC location is an estimate based on FCC sample AP510BFA. A separate GLB material receives a white emissive pulse only when an observed SoC code point is recent. This does not imply actual utilization between events, physical power, or hardware failure. Components with unknown locations and behavior without observed times receive no arbitrary glow. Reduced-motion settings are respected.

The original GLB is retained; report generation makes a derivative where only the SoC mesh has a separate material. Independent audits of two actual saved normal/unknown-marker runs and Chrome desktop/mobile checks covered stage states, scrolling, actual emissive material, and stop indication. Twenty-one related unit tests and a check that the derivative material uses one mesh passed. Additional device initialization/physical chip mapping outside observed scope remains unknown.

## English report display (bw-0598)

Screen and accessibility labels, stages, and status wording were unified in English. Normal and expected-stop results were reaudited; Chrome desktop/mobile checks covered translated display, stopped state, and remaining Korean. The then-current tunnel report was updated to the same result.

## Detailed UART observation (bw-0600)

Timestamped UART1 lines and UART0 DMA were added to the actual timeline under the detailed profile; original NOR/filesystem/BLE logs were also reflected in boot stages. Legacy runs without times continue to open using the previous method, and unknown times are not invented. Same-run drop/byte comparison and a separate 12-second input-failure test are documented in [detailed observation](../bootloader/detailed-boot-trace.md).

## Fixed board viewpoint and mobile logs (bw-0601)

Automatic front/back switching on stage change was removed. The board rotates only through the user's Front/Back controls or dragging. Separate materials for two estimated components with recent observations, SoC (Back) and NOR (Front), flash green, and the side to display is stated beneath the board. This is not physical evidence that these are continuously active or the only components in use; evidence for other components' actual positions/behavior was insufficient. Reduced motion uses static color.

The mobile footer grid expanding to fit all log content was fixed with a fixed height and internal vertical scrolling. Long data wraps within available width. Chrome checks covered widths 320/375/390/430 and desktop, viewpoint preservation across 0/3-second time changes after manual Front selection, green material values for SoC/NOR, log-bottom retention/width, and failure reports; 22 unit tests passed. New normal/failure reports were independently reaudited. Two reproducible intermediate reports were cleaned up.

## Multiple-event 3D representation (bw-0602)

The user requested showing as many observed components as possible while labeling uncertain physical locations as estimates. Separate event streams are used for SoC PC/UART/frame, NOR-related firmware logs, virtual touch input, EM9305/BLE-related firmware logs, and guest frame events. When multiple events overlap, GLB materials for SoC, NOR, touch, BLE, and display appear green simultaneously. The 0.7 seconds after an event is a visual visibility window, not actual device occupancy/activity duration. If no event falls within 0.7 seconds, it is not arbitrarily illuminated.

Estimated AP510BFA, U25643, and CY8C40 placement is based on the FCC sample. BLE location is unknown and the reverse upper-middle package is an arbitrary proxy; Display location is unknown and the central connector is an arbitrary proxy. Touch* maps accepted GPIO input to the estimated CY8C40 package, not evidence of an actual controller transaction. BLE*, Display*, Touch*, and explanations identify illustrative placement. These estimates do not claim actual physical location/component identity on the user's device. No arbitrary timeline is generated for ADC/IMU and other saved counters without timestamps.

Checks covered independent reaudit of normal capture, retaining the short failure report provided to the user, 22 related unit tests, Chrome desktop/mobile simultaneous green SoC+NOR, SoC+BLE*, and SoC+Touch*+Display*, and all indications off during an unrecorded six-second interval. Manual viewpoint and mobile log scrolling remain. The failed first report and reproducible intermediate reports were cleaned up.

## Both board sides and cumulative observations (bw-0603)

At the user's request, Front/Back of the assembled board were placed simultaneously as independent 3D views. They do not rotate automatically with the timeline; each can be manipulated by the user. Bare PCB switching applies to both. F/B on component badges indicated the side and selecting one focused the corresponding view.

Observed components remain green cumulatively up to playback time; only events within the last 0.7 seconds flash. This is not a utilization or continuous-activity claim. Touch*, BLE*, and Display* physical locations use the illustrative mapping described above, and devices without records are not shown. Chrome desktop/mobile checks covered absence of future observations at zero, loading both 3D views and Bare PCB, normal and 12-second failure, and log width/scrolling. Twenty-two related unit tests passed. Original board assets were unchanged.

## No display data and IMU observation (bw-0604)

Visual FRONT/BACK text in the two board views and F/B component-badge labels were removed. `NO DISPLAY DATA` is displayed at times with no screen capture. A separate pinned runtime was built to read the existing IMU GAF model's last RequestedAt/TriggeredAt after termination and ran the same stock boot experiment. The final trigger of that IMU model service was added to the event timeline/component stages; the IMU* 3D location is an unsupported illustrative proxy. This functional model does not support calculation and does not mean actual IMU measurements or completed sensor fusion. Individual ADC times and an independent chip location were unavailable, so times were not invented and it was not shown as a separate physical component.

Independent audit of the new run confirmed original handoff context, PC order, UART1, matching first four UART0 requests/responses, and zero faults. However, separate runs stopped host polling at about 20.0222 and 20.2117 seconds, and complete UART0 bytes and request counts (4 vs 5) did not match. Do not claim equivalence or observation noninterference. Evidence is in `private:simulator/imu-observation-native-bw604-01`, `private:simulator/imu-observation-bw604/comparison.json`, and `private:report-bw604`. In the experiment, IMU trigger is at virtual 13.4326678 seconds with two services / zero calculations. Twenty-three unit tests and Chrome mobile/desktop checks covered pre-capture text, absence of both-side labels, IMU flashing, and the remote tunnel.

## Desktop video capture (bw-0605)

At the user's request, Chrome playback of audited `report-bw604` HTML at 1440×900 was recorded from start to finish. The MP4 is about 23.6 seconds, H.264, 1440×900, replaying 20.826 virtual seconds of records. The final frame showed guest display, both board sides, and logs. This is playback of a saved virtual-execution report, not a live physical device or new firmware execution. Duplicate original WebM and temporary FFmpeg integration were cleaned up; the MP4 is retained at `personal-agent/output/blackwall-preview/blackwall-desktop-emulator.mp4` and in the tunnel report folder requested by the user.
