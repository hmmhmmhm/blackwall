# App Reprocessing After Reset Across Three Originals

bw-0418. **Stock 2.4, stock 2.3, and Faceclaw38 all reprocessed a new connection and ATT time message after a virtual reset during actual ARM main execution.** The existing stock 2.4 run was reused; only the other two originals ran anew. All three confirmed one RTC commit and original consumer return, with strict guard/architectural fault/memory violations 0.

Full E06 completion is not yet declared. Next independently verify post-reset memory access protection and state lifecycle/retention. Overall acceptance remains 8/16=50.0%, display checklist 3/6. This result is not integrated display, normal GAF, unlimited app behavior, or physical G2 sleep/recovery certification.

Follow-up bw419 [post-reset memory protection lifecycle](reset-memory-protection-lifecycle.md) found and corrected a read-path reset defect. This document's bw418 inputs/audits remain preserved; corrected-candidate runs are separate captures.

## Same behavior contract, different original ABI

All three executed actual original code for:

1. Run from main reset through existing virtual connection/ATT message and RTC update.
2. Re-enter original vector/SP via external virtual NVIC AIRCR SYSRESETREQ input.
3. Pass original retention configuration, WFI, sleep caller return, and CPDLP0 restoration.
4. Reinitialize original services and update RTC again with a new virtual connection and ATT message.

| Original | Retention store / return | After WFI | Sleep caller return | App consumer return |
| --- | --- | --- | --- | --- |
| Stock 2.4 | 0x4956e2 / 0x44df60 | 0x44e176 | 0x4765e2 | 0x492ce2 |
| Stock 2.3 | 0x4897fa / 0x44d670 | 0x44d886 | 0x4718ca | 0x486f06 |
| Faceclaw38 | 0x4897fa / 0x44d670 | 0x44d886 | 0x4718ca | 0x486f06 |

Addresses were not guessed with blanket offsets. Pinned main SHA, original setter/configuration constants, normal/deep caller BL and argument 1, WFI/ISB, flush literal, and IRQ32 vector were verified per original. Address substitutions applied only to observation points and host boundary checks. ARM image, branches, returns, WFI, and PC/SP were not modified.

Shared strict model SHA256 `fc3798cbf046be401c6039c2cce7f0b9a5df669d3f6d2be608482a481a1ac647` and observation class assembly source `11025f468daad40213cf6b4a8cd72340c0b489a6d8912074dad2402be175548e` are the same in all three cases. Existing board parameters such as GPIO/HAL callback addresses retain each original's E13 input.

## Execution inputs and reproduction

`reset_restart_profiles.py` verifies ABI from pinned originals. `reset_restart_inputs.py` constructs new execution inputs only from pinned E13 and bw417 parent inputs. It does not retroactively read current candidate models or latest upstream sources. `probe_reset_restart_versions.py` saves those inputs and runs them in the pinned Docker image.

Sixteen stock 2.4 regenerated execution inputs are byte-identical to existing successful bw417 inputs. Sixteen stock 2.3 inputs also matched before and after separating generation logic into a pure input-construction function. Inputs and audit tools are frozen and preserved. New tools can prepare/run using private Python without the existing package wrapper.

```sh
<private-python> tools/probe_reset_restart_versions.py <simulator-root> <new-output> --case stock23
<private-python> tools/verify_reset_restart_versions.py <simulator-root> <existing-capture> <new-audit>
```

`--case` is stock24/stock23/cfw. Different runs are sequential. One GiB free space is required before a new run; existing output is not overwritten. Success here is the declared original reset scenario, not completion of all E16 tooling.

## Results and limits

All three confirmed restarted-service controller 59 commands/events 0, events 1 after new connection, events 3 after new ATT, one RTC commit, and `2023-11-14T22:13:20.03`. Between first and restarted app behavior are RTC 2000 epoch/commit 0 and controller Unreleased/commands/events 0 reset states, so retained previous results alone are not treated as success.

Renode's first complete deep-sleep prefix was 21.2058 ms for stock 2.4, 24.8793 ms for stock 2.3, and 18.2288 ms for Faceclaw. Each original vector's IRQ32 and xPSR exception 48 were subsequently confirmed. These are virtual times of different software runs, not performance comparisons or measured physical sleep times. Complete causality of direct wake and observer neutrality remain unverified.

All three subsequently overflowed the 128-event buffer. Only the preserved first complete sleep/IRQ prefix is verified; full histories remain incomplete.

SRAM differences between pre-request and reset entry were 204/121/236 bytes, with 28.6/40.1/50 µs elapsed from request to entry respectively. Since existing code can execute before asynchronous reset, these are not used as pure reset-retention/loss evidence. Initial reset retention of KV/NV backing and ITCM was hash-compared, but independent tests of post-reset protection hook/MMU state and entire retained regions are next. This is not generalized to full LittleFS or physical retention verification.

## Audit

Saved audits contain 30 checks for stock 2.4 and 31 each for stock 2.3/Faceclaw. They check 16 original inputs, board/runtime, eight SRAM snapshots/hashes, logs, reset vector/count, retention/WFI, service/connection/app effects, and first sleep/IRQ prefix.

Five semantic counterexamples—lost RTC commit, wrong version boundary, reset count, another version's ISR, and NOR loss—and two original/case mismatch or tampered-original cases were rejected. Fourteen progress-management checks passed. Shared model is byte-identical to bw417, so existing 89 unit checks were reused without repeating unnecessary native/peripheral unit tests.

Evidence: private `simulator/reset-restart-version-native-01/{stock23,cfw}`, existing `cpu-retention-preparation-native-06`, and `reset-restart-version-research-01/manifest.json`. Proprietary images, SRAM, and NOR remain outside Git. No physical access, writes, Astra/subagents, or external publication occurred.
