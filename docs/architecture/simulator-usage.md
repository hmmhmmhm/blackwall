# Running the firmware simulator

> 2026-11-13 bw342: The active scope is emulator-only scope v3. For current status and reproduction, prioritize the [capability catalog](emulator-capability-catalog.md); for next steps, use the [emulator roadmap](emulator-roadmap.md). The following records earlier stages; do not treat historical progress, priorities, or the initial CPU table as current status.

At this stage the tool is a research runner that executes actual pinned firmware and stops at unimplemented accesses. It does not reproduce the entire G2, screen, or wireless devices. It has no function for connecting to physical hardware.

## Run in the current environment

Run from the Blackwall repository. Keep firmware and results outside Git. The input below is the official 2.4 bundle, already pinned and checked by SHA256. The tool does not automatically allow arbitrary other firmware.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" tools/firmware_runner.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  --scenario startup-lp-hypothesis \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-run.json"
```

`--output` must be a new file; existing files are not overwritten. The [persistent local environment](../getting-started/simulator-environment.md) is currently used. Pinned wheels and an offline generator are prepared for macOS arm64/Python 3.14. Distribution for other platforms is not yet available.

## Meaning of the profile

`startup-lp-hypothesis` in `tools/simulator-scenarios.json` explicitly bundles the virtual state constructed so far: isolated main reset execution, LP, reset latch=2, peripheral off, core/EPU/RAM ON, cache-off query, limited system register storage, and an instruction-clock watchdog. It is not an initial state obtained from actual glasses.

The default instruction limit is 10 million and wall timeout is 15 seconds. Change limits with `--instructions` and `--timeout-us`. Mixing a profile with manual model switches stops with an error. Use of a profile does not itself establish installable or hardware-validated status.

The report's `execution_scenario` records profile name, catalog SHA256, actually applied options, and limits. It also records original/main SHA, approximate CPU model, stop location/access type, register/RAM hashes, and model-specific limits. Results with different catalog hashes are not treated as tests with the same initial state.

## Reading results

- `unsupported-*`: Required CPU or peripheral functionality is not yet available. Execution does not continue using arbitrary values.
- `instruction-limit` / `time-limit`: Execution reached a limit, not boot success.
- `watchdog-*-due`: An event time was reached under a virtual clock assumption. This does not reproduce actual reset or interrupt.
- `uninitialized-itcm-execution`: Evidence of initialization of execution bytes was not obtained.

At this checkpoint, profile runs of all three images stop at a WICCONTROL read. Detailed evidence and model progress follow the [runner verification record](simulator-runner-status.md). There is no screen output because the actual firmware display path has not yet been connected.

## Extended profile reaching WIC configuration

Selecting `--scenario startup-lp-wic-config-hypothesis` in the same command adds WIC mode storage. It does not implement sleep/wakeup. This profile currently stops at the next MCUCTRL status query, 0x400201bc. Both profiles stop with `unsupported-sleep-boundary` if they reach WFI/WFE. Actual screen display is not yet available.

## Info1 source branch comparison

`startup-shadow-mram-hypothesis` and `startup-shadow-otp-hypothesis` inject different Info1 source bits of SHADOWVALID into the WIC profile. Both assume VALID=1 and other bits=0. Actual OTP/information-area data is not supplied.

At this checkpoint the MRAM profile stops reading information-area address 0x42003310; the OTP profile stops at a device power-up request. Neither establishes actual device information source, security state, or installation compatibility. Device data is not filled arbitrarily to produce success.

## Invalid calibration information tests

`startup-invalid-trim-zero` / `startup-invalid-trim-erased` are test fixtures providing only 0 / 0xffffffff respectively for the single Info1 TRIM_REV word. They do not provide an actual calibration image. The names describe test-input intent, not a judgment that firmware necessarily rejected it. Both inputs currently stop on the next unsupplied PATCH_TRACKER0 read. Other information/OTP data and information-area writes remain unsupported.

## Invalid input tests for three information words

Select additional error-input tests with `startup-invalid-info1-metadata-zero` / `startup-invalid-info1-metadata-erased`. Unlike the trim-only scenarios, they provide the same 0 / 0xffffffff only for TRIM_REV, PATCH_TRACKER0, and FT1_GDR1. They do not provide valid device calibration or select actual chip revision. All three images currently stop at 0x4002000c after reading each word once. Unsupplied words, partial-width reads, and information-area writes remain rejected.

## Chip revision assumption branch comparison

`startup-zero-info1-rev-21-hypothesis`, `...-22-hypothesis`, `...-23-hypothesis`, and `...-24-hypothesis` combine the three Info1 zero fixtures with synthetic CHIPREV. They do not read or verify the device's actual revision or calibration. Depending on the value they stop at different next accesses; results and execution scope are recorded in the [power management branch investigation](../research/spot-classification-research.md). Existing scenarios retain the unsupported CHIPREV boundary.

## Observed power configuration storage test

`startup-zero-info1-rev-22-spot-storage-hypothesis` / `startup-zero-info1-rev-23-spot-storage-hypothesis` add storage and readback of observed ACRG/VRCTRL settings. Actual analog power behavior and voltage stabilization are unimplemented. Both stock versions and Faceclaw currently stop at the next 0x40021018 read. See the [power management investigation](../research/spot-classification-research.md#restricted-storage-of-observed-power-settings) for initial values and permitted scope.

## Memory power state test

`startup-zero-info1-rev-23-memory-on-hypothesis` provides only TCM/NVM0/NVM1/ROM ON and cache OFF states. `startup-zero-info1-rev-23-rom-disable-hypothesis` additionally handles a single ROM-disable under a zero-delay assumption. This does not reproduce actual power state or response time. ROM re-enable and TCM/NVM power changes stop execution. See [model scope and results](../hardware/cpu-memory/memory-power-model.md).

## Memory retention configuration storage test

`startup-zero-info1-rev-23-retention-storage-hypothesis` adds storage of two MEMRETCFG bits. Actual sleep/retention/wake-up is not implemented; execution still stops at WFI/WFE. All three images currently stop at the next shared SRAM status read, 0x40021028. See [scope and results](../hardware/cpu-memory/memory-power-model.md#memory-retention-configuration-storage-model).

## Shared SRAM status and retention configuration test

`startup-zero-info1-rev-23-shared-sram-on-hypothesis` provides only a virtual ON state for 3 MiB shared SRAM. `startup-zero-info1-rev-23-shared-sram-retention-hypothesis` adds retention configuration bit storage. Actual bank power transitions, sleep, and retention are unimplemented. All three images in the second scenario stop at the next control address read, 0x40021040. See [scope and results](../hardware/cpu-memory/memory-power-model.md#shared-sram-on-state-and-retention-configuration).

## Shared SRAM override storage test

`startup-zero-info1-rev-23-shared-sram-override-hypothesis` stores only observed MMSOVERRIDE settings. GFX/DISP power effects are unimplemented. The next boundary for all three images is a 0x40004044 read. Follow [model scope](../hardware/cpu-memory/memory-power-model.md#shared-sram-override-configuration-storage). For input CRC handling in repeated runs, see the [verification performance record](../research/package-validation-performance.md).

## CLKGEN control value storage test

`startup-zero-info1-rev-23-clock-gates-hypothesis` stores only observed CLKGEN MISC/CLKCTRL values. Clock frequency, ready, and stabilization are unimplemented. All three images stop at the next MCUCTRL address read, 0x40020448. Follow [model and source verification](../hardware/power/clock-control-model.md).

## ADC delay configuration storage test

`startup-zero-info1-rev-23-adc-delay-hypothesis` stores only the observed AUDADCPWRDLY value. ADC power-up, sampling, and actual delay are unimplemented. All three images stopped at the next 0x4002036c read. Follow [scope and results](../hardware/sensors-input/adc-delay-model.md).

## Trim cache public reset fixture test

`startup-zero-info1-rev-23-trim-reset-hypothesis` provides only public-document reset values as read-only for 12 registers in the observed cache range. Actual device calibration and voltage behavior are unimplemented. All three images passed the cache completion flag storage instruction and stopped at the next 0x4002037c read. First check [sources, documentation differences, and model scope](../hardware/power/trim-reset-fixture.md).

## Power static-select configuration storage test

`startup-zero-info1-rev-23-power-switch-hypothesis` stores only observed PWRSW0/1 values. Actual rail switching, voltage, and ready are unimplemented. All three images stopped at the next power management function's 0x400211a0 read. Follow [model and results](../hardware/power/power-switch-model.md).

## TON power control configuration storage test

`startup-zero-info1-rev-23-ton-configuration-hypothesis` stores only observed TON configuration. Counter, comparator, voltage behavior, and LP override activation are unsupported. All three images passed the setup function and stopped at the next 0x40008858 write. Follow [sources, allowed values, and verification limits](../hardware/power/ton-configuration-model.md).

The current implementation is a [partial system emulator](simulator-scope.md), not full chipset reproduction.

## HAL clock recovery state storage test

`startup-zero-info1-rev-23-hal-state-hypothesis` stores only HALSTATES 0/signature values. Actual clock recovery is unsupported. All three images completed signature storage then stopped at the next 0x400211c8 read. Follow [confirmed meaning and limits](../hardware/cpu-memory/hal-state-model.md).

## Isolated CFW screen test

The [CFW renderer probe](../archive/cfw-renderer-probe.md) builds and executes actual g2flash drawing source as ARM code to generate a 576×288 PNG. This is separate from the main reset profile's boot screen above. The first display test is complete, but full firmware and display transport are not yet connected.

To run the four-frame test in the persistent environment, specify a new output path.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" tools/render_cfw_probe.py \
  "$HOME/Library/Application Support/Blackwall/simulator/upstream/g2flash-845f665" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-render" \
  --scene tests/fixtures/renderer-sequence.json
```

Results verified in an actual new environment are in `renderer-sequence-02/`. This timeline is a host-specified frame sequence, not a firmware animation clock or actual FPS.

## Execution through memory LDO setup

`startup-zero-info1-rev-23-memldo-setup-hypothesis` adds storage of two memory LDO fields after core LDO reduction and enable to existing control-storage conditions. It does not provide actual power stabilization; all three images stop at the `0x40021108` read. Reproduction commands for this profile and original helper checks follow the [setup verification record](../hardware/power/memldo-post-enable-setup.md). Full boot and main's actual screen path are not yet connected.

## Buck status branch tests

`startup-zero-info1-rev-23-buck-status-off-hypothesis`, `startup-zero-info1-rev-23-buck-status-lp-hypothesis`, and `startup-zero-info1-rev-23-buck-status-active-hypothesis` explicitly provide the post-enable state once. They are not actual power response or automatic transition models. ACT stops at VREFGEN4 write; default OFF/LP paths stop at first cache-control access. The unsupported Renode cache difference found in the initial comparison is addressed by the later optional instruction-memory model. Reproduction commands and verification limits follow the [status branch record](../hardware/power/buck-status-branch-fixtures.md).

## Functional instruction memory model

`startup-zero-info1-rev-23-buck-off-coherent-icache-hypothesis` and `startup-zero-info1-rev-23-buck-lp-coherent-icache-hypothesis` use optional I-cache control and the engine's coherent instruction memory. They do not reproduce actual cache delay, replacement, or power. Twelve combinations across both engines matched at the next PFCR write; the option-off path stops at the first ICIALLU write. Follow [reproduction commands and limits](../hardware/cpu-memory/coherent-instruction-cache-model.md).

## PFCR control storage

`startup-zero-info1-rev-23-buck-off-prefetch-storage-hypothesis` and `startup-zero-info1-rev-23-buck-lp-prefetch-storage-hypothesis` provide only PFCR storage after the first explicit write. Twelve combinations across both engines stop at the next D-cache selection write. Initial values, physical prefetch, and cache geometry are not provided. Follow [reproduction commands and verification scope](../hardware/cpu-memory/prefetch-control-storage.md).

## Functional data memory model

`startup-zero-info1-rev-23-buck-off-coherent-dcache-hypothesis` and `startup-zero-info1-rev-23-buck-lp-coherent-dcache-hypothesis` provide document-based 64 KiB D-cache geometry and set/way initialization and maintenance commands. For native execution add `--coherent-dcache-model` to existing options. Twelve actual-main combinations across both engines matched at the second buck status read after cache enable/clean. Physical cache, power response, and full boot remain incomplete. Follow [reproduction commands and limits](../hardware/cpu-memory/coherent-data-cache-model.md).

## Explicit buck response and initial VDDF storage

`startup-zero-info1-rev-23-buck-response-active-hypothesis` enables virtual ACT response and one VDDF storage after request and LDO setup. `...-stuck-off-hypothesis` is a failure input. Native options are `--buck-response-model active --vddf-tempco-storage`, not selected together with a single `--buck-status-fixture`. The response is assumed instantaneous, not an actual power model. Six actual-main combinations matched at the next clock-request write. Follow [details and reproduction](../hardware/power/buck-state-response-model.md).

## HFRC2 and MCU performance transition response

`startup-zero-info1-rev-23-mcu-clock-nominal-hypothesis` connects HFRC2 ready and HP request/ACK/STATUS on top of existing buck ACT/VDDF storage. Put `hfrc2-unready`, `no-ack`, or `denied` in the same prefix to select a failure response. These responses were verified at model-unit level, not every actual-main failure recovery branch.

To add `--mcu-clock-response nominal` to the native runner, provide prerequisite options including explicit power mode, active buck response, VDDF storage, and HAL storage. The six-combination comparison command follows. Input is the existing verified bundle directory and output is a new path. The 15-second host execution window is not a hardware time or performance measurement.

```sh
python tools/compare_dcache_startup.py <private-inputs> <new-private-output> \
  --buck-response active --mcu-clock-response nominal
```

Python and native stop at different points because of MPU support differences. This command explicitly checks that difference. See [model and verification scope](../hardware/power/hfrc2-mcu-mode-response.md).

## Native GPU power selection storage

Adding `--gfx-power-storage` to the existing native command supports GFXPWRSWSEL and legacy GFXPERFREQ storage under the peripheral-off startup assumption. It does not execute the GPU.

```sh
python tools/compare_dcache_startup.py <private-inputs> <new-private-output> \
  --buck-response active --mcu-clock-response nominal --gfx-power-storage
```

This comparison explicitly checks the difference between the Python MPU boundary and native subsequent HFRC write. Also check [GPU model scope and evidence](../hardware/display-gpu/gfx-power-selection-storage.md).

## Native HFRC force control

Adding `--hfrc-force-control` to the existing explicit clock response provides MISC.FRCHFRC and force-derived HFRC enable. This is not a physical clock model.

```sh
python tools/compare_dcache_startup.py <private-inputs> <new-private-output> \
  --buck-response active --mcu-clock-response nominal --gfx-power-storage \
  --hfrc-force-control
```

Check [control model, assumptions, and different execution boundary](../hardware/power/hfrc-force-control.md).

## Native GPU power preparation

Adding `--gpu-power-preparation` to the existing explicit HFRC/GFX stages supports one current synthetic PCM2 HP preparation cycle. The next GPU enable request remains blocked.

```sh
python tools/compare_dcache_startup.py <private-inputs> <new-private-output> \
  --buck-response active --mcu-clock-response nominal --gfx-power-storage \
  --hfrc-force-control --gpu-power-preparation
```

Check [model and unsupported branches](../hardware/display-gpu/gpu-power-preparation-sequence.md).

## Native GPU power response

Adding `--gpu-power-response active` to preparation provides a nominal GPU bit 18 response on the first status read. It is not a physical power or GPU engine model. `stuck-off` can be observed separately in the runner and does not guarantee automatic recovery.

```sh
python tools/compare_dcache_startup.py <private-inputs> <new-private-output> \
  --buck-response active --mcu-clock-response nominal --gfx-power-storage \
  --hfrc-force-control --gpu-power-preparation --gpu-power-response active
```

Check [response model and failure observation](../hardware/display-gpu/gpu-power-domain-response.md).

## GPU initialization analysis

`tools/analyze_gpu_initialization.py <inputs> <comparison-report> <new-output>` checks the existing GPU power response six-combination report and three pinned firmware inputs and extracts static IRQ initialization patterns. It is not a GPU execution or full boot command. Check [sources, IRQ28 test, and limits](../hardware/display-gpu/gpu-initialization-research.md).

## GPU idle clear

Add `--gpu-interrupt-clear` to existing power response options. This requires power response and supports only IRQ clear 0 in the on state. GPU command execution, completion interrupt, and reset are unsupported. Check [model, execution results, and connection failure history](../hardware/display-gpu/gpu-interrupt-clear-model.md).

## Initial GPU ID and ring capture

Adding `--gpu-id-initialization` to power response and idle clear allows one observed initial 0 write, blocks the next 0xec, and records bounded SRAM candidates. `tools/analyze_gpu_ring_capture.py <static-report> <new-output> --runtime-report <report>` accepts repeated runtime-report arguments for three inputs and checks hashes, static calls, and byte footer relationships. It is not a GPU execution or full boot command. Check [model, limits, and evidence](../hardware/display-gpu/gpu-id-initialization-capture.md).

## Initial GPU ring configuration

Adding `--gpu-ring-configuration` to the initial ID stage stores ec/f0/f4 configuration once. It checks range, order, and length policies but does not support subsequent submission, reads, or command execution. After CPU stop, the configured mapped SRAM ring range is preserved as a snapshot. Check [supported scope and actual next boundary](../hardware/display-gpu/gpu-ring-configuration-model.md).

## Fixed GPU ID response

Explicitly specifying `--gpu-identity-response source-reset` at the ring configuration stage provides the public/firmware fixed ID. `absent` is 0 for negative testing, not an actual device ID. Unsupported commands, ID writes, and reads before configuration remain blocked. Check [sources, selection conditions, and failure observation](../hardware/display-gpu/gpu-identity-response-model.md).

## Initial GPU reset requests

Adding `--gpu-initial-resets` to the source-reset ID response accepts the observed e8=0 → fc=0 initial requests once each. Active GPU reset is unimplemented and ring configuration validity is marked unconfirmed. Unsupported 0x388 writes, status reads, and command execution remain blocked. Check [limits, status, and execution evidence](../hardware/display-gpu/gpu-initial-reset-controls.md).

## GPU register name investigation

`tools/build_gpu_register_catalog.py <pinned-nema-regs.h> <new-output.json> --address 0x40090388` looks up literal names in the official SDK. The [pinned catalog](../data/gpu-sdk-register-map.json) includes 106 offsets and separate command constants. It does not connect hardware, execute GPU, or permit writes. Check [sources, verification, and limits of meaning](../hardware/display-gpu/gpu-extension-register-research.md).

## Raster initial-value observation-only mode

`--gpu-raster-init-storage` records the observed write of 1 only once after the initial reset option. It is trace_only=true; raster effects are unimplemented. Progress in this mode is not used as GPU/boot verification. Check [actual pending prefix, limits, and correction](../hardware/display-gpu/gpu-raster-init-storage.md). Repeatedly specify runtime-report for three pinned inputs to `tools/analyze_gpu_pending_init.py <new-output> --runtime-report <report>` to compare observed initial prefix candidates. It is not a general decoder.

GPU CONFIG observation options and unverified high/STATUS branches follow the [CONFIG boundary record](../hardware/display-gpu/gpu-config-submission-observation.md). CONFIGH is not automatically filled from low alone. Following the power-off [static investigation](../hardware/display-gpu/gpu-power-off-research.md), an [opt-in response model](../hardware/display-gpu/gpu-power-off-model.md) was added. Default options continue to block on→off requests; `--gpu-power-off-response off|stuck-on` requires an explicit STATUS=zero hypothesis and active power profile. Reactivation and retention are unsupported. This option does not verify full boot or integrated screen.

Post-off PCM2 trim storage transitions are selected separately with `--gpu-off-sequence-storage`. It requires an explicit off response and supports only 18 writes with exact field/order. Check [analysis and verification](../hardware/display-gpu/gpu-post-off-power-sequence.md). This is not an option for full boot, GPU reactivation, or screen success.

`--gpio-config-storage` supports only the protection key and readback of guest-written PINCFG. Initial pin values, input/output, and IRQ are unimplemented; unwritten reads are blocked. Follow [source and verification record](../hardware/power/gpio-config-storage.md). It is not a full boot or screen success option.

`--gpio-interrupt-idle` is explicitly selected with `--gpio-config-storage`. It supports only EN storage and recording 0 STAT/CLR requests; external events, SET, and CPU IRQ generation are unsupported. Check [hypothesis and verification scope](../hardware/power/gpio-interrupt-idle-model.md).

`--gpio-output-latch` supports only WT/WTS/WTC storage transitions for guest-configured GPIO push-pull pins. Reserved-only, unconfigured, and other mux/output modes are blocked. `--capture-itcm-prefix` is a diagnostic option that reads 256 bytes of virtual ITCM after stopping. Check [scope and verification](../hardware/power/gpio-output-latch-model.md). This does not imply actual pad/device behavior or full boot success.

`--adc-info-zero-fixture` requires MRAM source and zero metadata. It supplies 0 to five temperature/ADC calibration words to test actual firmware fallback, not valid factory calibration. `--capture-sram-window ADDRESS:BYTES` is a diagnostic reading bounded aligned virtual SRAM. Check [analysis and verification](../hardware/sensors-input/adc-info-zero-fixture.md).

`--adc-calibration-control` supports only the source-supported initial ADCCAL word 1 and bit 0 storage. Read-only completion bit is 0; actual ADC engine/power/conversion completion is not implemented. Check [control scope and verification](../hardware/sensors-input/adc-calibration-control.md).

`--adc-power-response active|stuck-off` is selected with the GPU power model and ADCCAL storage. It preserves other bits in the shared bank and provides virtual request/status bit responses when ADC autocalibration is off. It does not imply an actual rail, ADC ready, or conversion. Check [scope and failure observation](../hardware/sensors-input/adc-shared-power-model.md).

## Reproducing a pinned native profile

After Astra review, a command was added to reproduce bw122 runs of three originals without regenerating them. Follow [pinned profile usage](native-replay.md). It is separate from the RTC bw124 change and requires existing private inputs. Command success is not full boot, screen, or device recovery success.

## Bounded patch execution observation

A [bounded execution observation tool](bounded-execution-observation.md) was added to observe 30 instruction sites and 22 CFW direct targets in pinned stock 2.3/Faceclaw38. It does not change original instructions and confirmed an R2 difference immediately before the instruction after a heap-size change. This is not full trace or dynamic functional equivalence verification.

## RTC candidate reuse investigation

The [RTC module contract](../hardware/power/rtc-module-contract.md) records isolated virtual-time tests of a pinned Apollo4 candidate and static analysis of the original candidate writer. This research tool does not connect RTC to the current main board. The candidate's 15 checks are not an Apollo510 compatibility pass and include source discrepancies.

## Optional virtual RTC adapter

The [RTC adapter](../hardware/power/rtc-strict-adapter.md) can be selected with `--rtc-model epoch2000-100hz`. Counter writes are unsupported by default and unnecessary for current original progress. Epoch/clock/read-window and optional HAL write order are explicit assumptions. Distinguish this from full boot and physical oscillator evidence.

## Read-only virtual chip information

`--chip-info-profile source-reset-zero-ids` in the [chip identity contract](../hardware/cpu-memory/chip-identity-contract.md) uses the existing explicit revision and synthetic IDs. They are not actual device values; unconfirmed JEDEC remains strict. Only partial structures/memory calculations were verified; full lookup function/device compatibility unverified.

## Explicit JEDEC mock and first-hit observation

In the later [JEDEC experiment](../hardware/cpu-memory/jedec-mock-personality.md), execution reached lookup API return only in a virtual configuration specifying both `--jedec-mock-part` and `--jedec-mock-cid`. The previous section's unverified full lookup describes the state before this follow-up. Actual device identifiers remain unconfirmed. `--observe-pc LABEL:ADDRESS` and `--observe-sram LABEL:ADDRESS:WORDS` are read-only; the user must verify original instruction boundaries in advance. Unspecified JEDEC access retains strict stopping.

## IOM7 first request investigation

`tools/inspect_iom7_request.py SIMULATOR_ROOT NEW_OUTPUT` uses existing JEDEC comparison runs as input for read-only observation of original address/FIFO/CMD. The [investigation result](../hardware/power/iom7-first-request.md) reaches target 0x6b request 05 09; this tool does not implement peer response or full boot.

## IOM7 pointer-only diagnostic experiment

`tools/probe_iom7_pointer_main.py SIMULATOR_ROOT NEW_OUTPUT` derives bw133 pinned inputs. The [virtual pointer experiment](../hardware/power/iom7-pointer-probe.md) checks only whether a 1-byte read after the first pointer is reached; it does not return data. It is not automatic peer installation in the default main runner.

## Explicit ADC configuration profile comparison

`tools/probe_pmic_adc_config.py SIMULATOR_ROOT NEW_OUTPUT` sequentially runs four virtual values 0–3 and seven stock/CFW and unknown controls. It responds only to one register in the [configuration lookup experiment](../hardware/power/pmic-adc-config-probe.md) and stops at the next address. Do not interpret these as actual PMIC initial values.

## Complete PMIC restore function experiment

`tools/probe_pmic_restore_main.py SIMULATOR_ROOT NEW_OUTPUT` observes PMIC restore function returns and RAM flags across three originals with an explicit 7-byte readonly fixture. The [profile scope](../hardware/power/pmic-restore-profile.md) ends before the subsequent IRQ configuration write. It does not mean actual device state or full boot success.

## PMIC event initialization

`tools/probe_pmic_interrupt_main.py SIMULATOR_ROOT NEW_OUTPUT` runs three originals using an explicit idle bank and one existing strict control. Only the [IRQ register scope](../hardware/power/pmic-interrupt-initialization.md) is implemented; PMIC GPIO output and Apollo GPIO input are not connected.

## PMIC GPIO configuration storage

`tools/probe_pmic_gpio_main.py SIMULATOR_ROOT NEW_OUTPUT` stores only guest-written GPIO configuration in three originals plus one default control. It follows [scope and boundary](../hardware/power/pmic-gpio-storage.md) and does not implement pin status, voltage, or IRQ wiring. It currently stops before the next low-voltage charging enable request.

## PMIC charging configuration storage

`tools/probe_pmic_charger_main.py SIMULATOR_ROOT NEW_OUTPUT` runs three originals plus one default control. It follows [digital configuration and unknown scope](../hardware/power/pmic-charger-storage.md) and does not create battery measurements or actual charging behavior. It currently stops at a PMIC watchdog configuration request.

## Read-only observation of original timer arguments

`tools/observe_pmic_timer_profile.py SIMULATOR_ROOT NEW_OUTPUT` compares function-entry RAM and flash profiles of three originals without changing the model. The [contract with recovery feed](../hardware/power/pmic-watchdog-recovery-contract.md) distinguishes nominal timeout from unsupported repeated START and timer behavior.

## Common comparison of registered candidate screens

From bw434, specify both `--compare-baseline` and `--comparison-output` to the existing screen runner to obtain execution/saved audit, same-model comparison, and L8 PNG. Follow [commands, judgments, and current support scope](../hardware/display-gpu/display-cli-comparison.md). Distinguish native preservation marker verification from difference checks on synthetic records; this does not mean full UI/natural main completion.
