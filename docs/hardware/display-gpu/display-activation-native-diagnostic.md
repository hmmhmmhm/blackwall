# From original M55 API input to UI/display activation

Work bw-0341 resumed. Scope v3 E05/E09 and first-screen M2–M4 were investigated. **API diagnosis verified that original scheduler resumes UI and display tasks and original code changes display mode 0→1 in stock 2.4, stock 2.3, and Faceclaw38.** This is not evidence of completed pixel output or full main boot.

## Exact test boundary

1. Run existing pinned board/original main from reset. Normally pause the whole machine at an original function entry before unsupported IMU getter. Earlier original branches, returns, and image remain unchanged.
2. Afterwards is an **explicit API-test interval**. Host places a small test caller in emulated WORK and changes entry to original memcpy, which copies that caller into empty ITCM via guest instructions. This is not actual glasses RAM execution. Existing main memory policy remains enabled.
3. Caller preserves original Sensor task's Thread/PSP context and IRQ settings. It calls only original queue creation, UI message producer, and queue-get APIs. Host does not set original UI/Display PC, TCB, stack, or mode. Caller has no MSR/CPSID/CPSIE or direct jump to UI continuation.
4. Original queue send wakes UI; original RTOS restores UI's original stack. UI executes preparation helpers and sends display messages through a ROM table. Original display task then handles on message and writes mode 1.

Initial entry override and test-caller insertion are disclosed conditions. Do not report this as “resumed original main's stop unchanged to completion,” “sensor initialization completed,” or “processed an actual BLE packet.” Sensor's unknown 153-byte getter was neither extended nor returned as success.

Caller also contains code waiting on its own empty queue, but at the observed point the sending task had already been preempted in original port yield path. Dummy queue had zero receivers. Do not claim that wait completed or executed. Distinguish individual source helper/API returns from task resumption.

## Original path confirmed

UI type 2 API creates 12-byte `[2, app-id, payload-length]` and separate ring payload. In UI state 0→1 branch receiving type 2, four preparation helpers are called and display type 0/1 messages sent through ROM table `+0xc` and `+8`. Type 1 producer at `+8` is an indirect call not found by direct BL search alone.

| Point | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| UI type 2 producer | `0x445e74` | `0x445e18` |
| Original continuation after UI queue-get | `0x4455c0` | `0x445568` |
| UI display API table | `0x79daf4` | `0x7acdd0` |
| Table `+8`: display type 1 producer | `0x47ec82` | `0x47aa12` |
| Observation point after display mode 1 store | `0x47ea64` | `0x47a7fc` |

API input is app-id `0x10b`, also present at original call sites, and length 0. App name/final content format are not inferred from this number. Valid structure and activation causality at original API boundary were tested, not phone wire-packet authentication/service dispatch or every upper-caller condition.

In all three native positives:

- Actual current TCB, original task name, stack range, and Thread state for UI and display were cross-checked with SRAM/registers.
- Initial IRQ context PRIMASK/BASEPRI/IPSR were 0; PSP/PSPLIM were within original sending task range.
- UI state 0→1, original display queue delivery, and original mode 0→1 confirmed. Existing MSPI1/TIMER14 models used; 11 existing peripheral models and main bytes unchanged.
- Memory-policy violations, CFSR, HFSR were 0. Unsupported peripheral accesses were 0 through test checkpoint.

Stock2.4 type 3 control did not enter the same activation branch and stopped with UI state 0, mode 0, display messages 0, receiver 1. Type 3 is another valid message type; it is not interpreted as complete error handling of all malformed BLE packets.

## Standalone ARM versus board diagnosis

Extended `probe_display_queue_producer.py --activation` checks actual producer/queue/ring reads and UI state transitions for payload 0/4/16/10240 bytes across three originals. Input 10241 reaches diagnostic path before queue send but stops at standalone fixture TIMER14 access, so completed error return is unverified.

Standalone M7 UI preparation stopped at MSPI1 power read `0x40021004`, display-on callback at TIMER14 `0x400083c0`. Board model already handles these addresses, so execution continued on existing M55 board instead of creating new per-register models. M7 unmapped accesses are not reported as physical glasses or Renode board failures.

81 standalone original ARM and 81 frozen runs plus nine source-mutation negatives were checked. Existing type 3 queue probe 72 runs were byte-identical to earlier report. Observer on/off final-state comparison applies only to this M7 input, not proof of native hook noninterference or exact identity with unobserved boot.

## Execution and saved reaudit

Specify new output outside Git. Pinned baseline capture/contract and existing venv-02, Docker image, LLVM required. Arbitrary registration of a new CFW candidate remains E04.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/run_display_activation_m55.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  "$HOME/Library/Application Support/Blackwall/simulator/my-new-activation-capture" \
  --case stock24
```

Other baselines: `--case stock23` or `--case cfw`; activation-branch control: `--message-type 3`. This is a UI API diagnosis command, not full E16 product CLI. It rejects overwriting existing output and writing proprietary captures under Git.

```sh
# Audit saved results separately without new firmware execution.
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/run_display_activation_m55.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  "$HOME/Library/Application Support/Blackwall/simulator/my-new-activation-capture" \
  --case stock24 --audit-existing \
  --audit-output "$HOME/Library/Application Support/Blackwall/simulator/my-new-activation-audit"
```

122 native judgments passed across eight official diagnostic captures (three-image positives + stock24 type 3 under both pinned recipe and public command). Twelve semantic negatives mutating task owner, IRQ context, mode, and caller context were rejected. Rejection of capture output inside Git was confirmed. Results/model/hashes/reaudit code: private `simulator/display-activation-integration-verification-02/manifest.json`.

## Failed investigations and remaining work

Private prototype01 failed on CLR RegisterValue delivery; 02 attempted to restart an already aborted machine. In 03/04 another original task ran on a CPU-only-halted board before even the caller's first record and aborted at GPIO117 boundary. These are not classified as UI-code or input-message failures.

Two separate M55 core tests confirmed paused PC set/resume and time invariance during `Machine.Pause()`. Final recipe normally pauses whole machine and does not change IRQ masks affecting ISR judgment. General pause-design reference: [Renode's own pause test](https://github.com/renode/renode/blob/master/tests/unit-tests/precise-pause.robot); actual judgment on current 1.17 follows local evidence above.

Activation and mode 1 in prototype05/06 were verified. Prototype07 did not reach type 3 frame wrapper in 30-second observation after mode 1. Source UI task was running, but whether cause was insufficient valid content, app initialization path, or renderer dependency was not established. It is not grounds to allow new registers wholesale.

**M2 completed activation-input causality at API boundary.** Virtual phone/GATT input remains E13. M3 is partial: original activation preparation executed but frame type 3 preparation not connected. M4 is also partial: actual task resumption confirmed but original render calls unconfirmed. Next trace causality of valid content and original app dispatch → first draw/submit after mode 1. Overall 3/16, first-screen stages 2/6; full main and 576×288 pixels incomplete.

Follow-up bw344 confirmed original app dispatch/callback/return and narrowed the boundary to blocked one-byte MSPI0 receive. Follow [original app processing and first render entry](ui-content-render-ingress.md) for latest evidence and remaining boundary. Prototype07's unknown cause above is the historical status.
