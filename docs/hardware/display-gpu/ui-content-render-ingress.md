# Original UI application processing and first render-entry boundary

Below are bw344's results. Follow-up bw345 added JBD status transactions and confirmed actual renderer calls. Follow [latest evidence and remaining boundary](jbd-display-status-and-render-task.md).

bw-0344, E05/E09. **API diagnosis on stock 2.4, stock 2.3, and Faceclaw38 confirmed original app dispatch → registered callback → return and app-root publication.** All three were blocked by an unsupported one-byte MSPI0 receive request before first draw/submit. This is not evidence of full main boot, natural screen, or pixel success.

## Inputs and observation scope

The same main reset, virtual board, and API caller from [existing activation diagnosis](display-activation-native-diagnostic.md) were reused. The condition of inserting the caller after normal pause immediately before IMU getter remains. Main images and existing `strict.cs` peripheral model were unchanged. UI/Display PC, TCB, stack, mode, and firmware returns were not forced.

New `--trace-content` derives observation PCs from original code and registration table. It records counts and first r0–r3/SP/LR/instruction count for dispatch, callback, return, draw, target setup, submit, ring submit, display producer, and frame wrapper. Existing broad memcpy hook is excluded in this separate recipe. Observation configuration is an execution-setting change; exactness/noninterference against a hook-free run is not claimed.

Original API input is unchanged: app-id `0x10b`, payload length 0. UI message header and callback payload staging buffer are at different addresses. Statically identified argument path:

`UI type 2 → dispatch(app-id, 2, staging, length) → registered callback(2, staging, length, context[0x1c]) → UI continuation`

| Original point | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| Dispatch call PC | `0x4456e8` | `0x445690` |
| Dispatch function | `0x443832` | `0x443e9a` |
| Callback for app-id `0x10b` | `0x5f8e36` | `0x5ed1f6` |
| UI continuation after callback | `0x4456ec` | `0x445694` |
| Registry count | 52 | 46 |
| MSPI0 stop PC | `0x4e8a46` | `0x4db672` |

First callback arguments and instruction-count order, original UI stack range, and descriptor root field were checked in actual captures. User-facing app name and full UI completion are not inferred from numbers/pointers alone. Callback return and object publication do not mean rendering completed.

## Block identified before first submit

In all three images actual store target is `0x40060000`, value `0x10441`. Actual transfer descriptor read by original HAL and ARM code confirm length 1, instruction enabled, instruction `0x05`, receive direction. This is outside current model's specified `0x9f`/four-byte diagnostic RX contract. Guard rejected the write; aborted machines were not restarted.

Diagnostic `guard_iom7_tail` is a broad address-guard name. An MSPI0 address is not interpreted as IOM7 communication. `BlackwallMspi0Tx.TryWrite` in `tools/renode-mspi1-config.cs` currently permits receive combination `value==0x40441`, `instruction==0x9f`. Request `0x10441` differs and does not satisfy TX conditions either.

Actual connected device and response-byte meaning were not established. Do not infer flash/panel status from command number or insert 0 as ready response. Next define supported device transaction and failure controls by linking original caller, actual return-byte consumption, and same bus target/configuration.

Current observation counts in three images are dispatch 1, callback 1, return 1; draw, target, submit, ring submit, display type 3 producer, and frame wrapper all 0. Thus “no callback because valid content is absent” does not describe this input. App processing at explicit API boundary was verified; subsequent device transaction is the next dependency.

## Execution, audit, and judgment

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/run_display_activation_m55.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-capture-outside-Git> --case stock24 --trace-content
```

`stock23` and `cfw` are also supported. Content trace supports type 2 only. Recheck saved captures with existing `--audit-existing --audit-output <new-audit-path>`. API activation/dispatch verification and subsequent screen support are separate. Read output fields together: `ui_dispatch_verified=true`, `post_mode1_supported=false`, `frame_wrapper_observed=false`, `frame_pixels_verified=false`.

Evidence is outside Git in `simulator/ui-content-integration-verification-01/manifest.json`. Three actual board-diagnostic captures/69 judgments, rejection of 12 semantic mutations of callback arguments/order/stack/observation PCs, rejection of 27 source/registry mutations, and three original isolated M7 dispatches were checked. Three existing activation captures were also reaudited. Source helper matched frozen verified version by AST. This is not expanded into native-observer neutrality evidence.

## Failure history and corrections

- trace01 installed dispatch stop after mode 1 and missed the already-passed call. Earlier-installed watch had dispatch/callback/return. Do not assume a fixed single observation order between UI and display tasks.
- trace02 paused at individual UI points and installed display mode 1 stop too late, missing it. This is not mode-write failure. Actual mode 1, MSPI0 abort, and failed checkpoint judgment were preserved.
- Final recipe installs all content watches before first API resume, continues observation after existing display mode 1 checkpoint, and saves per-boundary counts and actual guard cause together.
- Saved auditor for first public stock24 run failed by reading context still 0 in SRAM immediately after activation. Original execution capture was preserved; auditor was corrected to compare context in mode 1 snapshot and verified by separate saved audit. This correction is not counted as firmware rerun or new native success.

Overall remains 3/16, first-screen checklist 2/6. Original app callback is confirmed, but M4 render calls and E05/E09 natural-execution conditions are not yet met.
