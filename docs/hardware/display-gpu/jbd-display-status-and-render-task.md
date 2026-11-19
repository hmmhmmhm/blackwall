# JBD4010 virtual status transactions and original render task

Follow-up bw346 progressed through runtime wake and command-packet generation. Follow [latest evidence](gpu-runtime-wake-and-command-packet.md). Below is bw345's historical record.

bw-0345, E05/E09. **In API diagnosis across stock 2.4, stock 2.3, and Faceclaw38, original status check → actual RTOS `ambiqdraw` task → original draw and output-target setup calls executed.** Submit, pixels, and natural main completion remained incomplete. Only first-screen checklist M4 newly completed; overall acceptance remained 3/16.

## Target and consumption rules for command 05

MSPI0 command 05 from [bw344](ui-content-render-ingress.md) was connected to original strings `jdb4010_status_check`, `driver.jbd4010`, `driver/uled/jbd4010/drv_mspi_jbd4010.c` and actual caller. Stock 2.4 function is `0x5bc308`, stock 2.3/Faceclaw38 `0x5b2d84`. SPI command number was not simply interpreted as flash status. This evidences **JBD4010 display driver expected by original firmware**, not physical chip identification.

| Original transaction | Failure determined by original | Next behavior |
| --- | --- | --- |
| Command `0x05`, receive one byte | Transport return nonzero or byte=`0x90` | Log error/event and return `-1` |
| Command `0x35`, receive one byte | Transport return nonzero or byte=`0` | Log error/event and return `-1` |
| Both checks pass | Neither condition above | Status check function returns 0 |

Original upper function has separate branch attempting recovery on abnormal status. Status-check failure is not interpreted as immediate whole-program termination. This test does not prove successful recovery or physical safety.

Standalone original M7 tests executed comparisons/branches **immediately after transfer return**. Across three images, all 256 byte values and transport errors 1/6/`0xffffffff` were checked, 1,554 cases total. No callee-return stub used; stop before next call/branch boundary. This test itself does not evidence actual receive transaction or full function completion. Native tests below separately verified actual original HAL, FIFO reads, and status-function return.

## Explicit virtual device profile

Opt-in `jbdStatusHex` in existing `BlackwallMspi0Tx` declares response bytes for both commands. Default is empty string and rejects requests as before. Existing command 9f/four-byte identity diagnosis remains separate.

- `5a01`: nonzero virtual response passing both checks.
- `9001`: control failing command 05; command 35 not requested.
- `5a00`: control passing 05 then failing 35.

These are **virtual test inputs with source-confirmed consumption rules**, not verified initial values, status meanings, or post-reset values of actual component. Model does not overwrite responses as always ready or skip firmware branches.

Only control `0x10441` receive-one-byte and commands 05/35 added; other commands/sizes/settings rejected. After existing virtual-time service, it provides a once-readable FIFO byte and records actual delivered count, completion, IRQ, and history. Overlapping transfers, discarding unread data, duplicate reads, clock/power loss, and incomplete cases were tested. Time model is not measured physical SPI speed.

## Original M55 results

As in existing [API activation recipe](display-activation-native-diagnostic.md), pause immediately before IMU getter after main reset and insert explicit test caller. Original main image, UI/Display/renderer PC, TCB, stack, mode, and callee returns are unchanged. Only one pinned MSPI0 configuration component changed. Saved audit replaces that component only in parent `strict.cs` and compares bytes with complete result.

| Scenario | Actual status-function return | Original draw / target setup | Subsequent boundary |
| --- | --- | --- | --- |
| Stock 2.4 `5a01` | 0 | Once each | `0x5c1e6e` |
| Stock 2.3 `5a01` | 0 | Once each | `0x5ba8c6` |
| Faceclaw38 `5a01` | 0 | Once each | `0x5ba8c6` |
| Stock 2.4 `9001` | `0xffffffff` | Zero each | Power/LDO boundary in upper recovery path |
| Stock 2.4 `5a00` | `0xffffffff` | Zero each | Power/LDO boundary in upper recovery path |

In three normal runs current TCB was `ambiqdraw` in original task graph and draw/target SP was within original stack range. Name, TCB, stack base/depth, current TCB slot, call order, and source-derived PC were cross-checked against actual SRAM/register data. Original UI/display task resumption and mode 1 also confirmed by existing judgments. **Render-task entry** is complete; this does not claim desired HUD was actually drawn.

Three normal runs' first draw was rejected by current startup-focused model at power/LDO request `0x40020080 ← 0x6d3d9`. Error controls also reached same address but through recovery path before renderer entry. Do not classify same address as same execution cause. GPU submission, display type 3 frame wrapper, and guest pixels are all unobserved.

New observations are first register sample and total hits per declared PC, not exhaustive traces of every call or exact identity with hook-free execution. Status-check counts differed by image/observation timing and are not interpreted as physical performance or equivalent instruction counts.

## Reproduction and saved audit

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/run_display_activation_m55.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  <new-capture-outside-Git> --case stock24 --trace-content --jbd-status-hex 5a01
```

`stock23`, `cfw`, and failure profiles above also supported. `--audit-existing --audit-output <new-audit-folder>` rechecks without changing existing captures. Distinguish `execution_passed` from schema2 `semantic_validation.passed`. Schema2 contract covers this API status transaction, not full main/screen acceptance. Actual render evidence is separately checked by `renderer.verified` and draw/target observations.

Pinned outside Git in `simulator/jbd-status-integration-verification-01/manifest.json`:

- Three normal/two error native captures and schema2 judgments, plus three original renderer-task verifications.
- Saved reaudits of three prior unsupported baselines. Old observer recipes/models make these bounded-invariant controls, not CPU/event exact controls.
- 15 response/return/renderer stack/owner/component mutations rejected. Renderer mutations reject promotion to render stage separately from status-transaction passage.
- New receive model 68 checks, existing TX 45 checks, 1,554 original post-transfer branch cases.
- Unchanged main, one component replacement, and hashes for source/model/tools/captures.

## Failure history and next work

First native stock24-01 failed after execution in telemetry by looking for `@ none` object as `sysbus.mspi0_tx`, so final trace was not saved and it was excluded from normal evidence. Lookup was corrected to shared guard's actual `Mspi0Config.Pio`, saving default SRAM/trace first; a separate cold run verified it. Source01 log-string literal-offset error was preserved as failure and corrected in source02. Unit red01 confirmed absent receive profile before green01/02. Aborted machines were not resumed.

Next connect **first draw GPU power/LDO reactivation → list generation → submission** as one behavior unit. Rather than simply allowing the next address, first identify startup-only power model versus runtime wake, field preservation, and failure/interruption contracts. M3 frame preparation and M5/M6 full pixels/reproduction remain.

Current overall 3/16=18.75% (displayed 18.8%), first-screen checklist including API diagnosis 3/6=50.0%. No glasses access or physical writes.
