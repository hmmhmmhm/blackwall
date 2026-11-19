# MSPI0 Retention Response and Natural Power-Down

bw-0310. Connected the [original contract](mspi0-retention-flags-contract.md) to an optional model. Natural M55 execution of stock 2.4, stock 2.3, and Faceclaw 38 passed MSPI0 power-down and clock gating to a new CPU power-control boundary. **Overall completion criteria remained 13/29 = 44.8%, scope v2.** Full boot and integrated display remained incomplete.

## Restricted response and lifetime

A CQFLAGS response is allowed only at the prepared original read PC with R1=`0x40060000`, power on, and queue/DMA/XIP inactive. Because bw309 confirmed matching paths and restoration writes for all 256 upper-byte values in that save/restore path, only software flags are supplied and the upper byte is an explicit zero fixture. This is not claimed as a general idle/completion response or actual hardware flags. Other readers, CQSTAT, and queue/DMA/PIO execution remain blocked.

Power-down requires all of:

- An explicit MSPI0 power owner and off-response profile.
- Inactive queue/DMA/XIP and IRQ enable cleared.
- A retention-flags read during that power cycle.

On a successful off response, a virtual lifetime profile resets the internal controller register bank and IRQ to source-reset state. This does not implement the panel's own power/content retention or all actual chip retention behavior. The controller is not reset without an off response. Original code performs clock gating and releases HFRC2 force through existing clock/core models.

The default profile retains prior behavior. The new power owner must be the same object in core and config; general MSPI1 NOR/PIO lifetime was not copied. Two models changed, core/config; seven other pinned sources remained unchanged.

## Natural execution results

| Input | Next PC | Next unsupported operation | MSPI0 result |
| --- | --- | --- | --- |
| Stock 2.4 | `0x44e10c` | 32-bit `CPUPWRCTRL(0x40021050)` read | powered-off, one controller reset |
| Stock 2.3 | `0x44d81c` | Same | Same |
| Faceclaw 38 | `0x44d81c` | Same | Same |

For all three, original literals, `ldr r0,[r0]`, and R0=`0x40021050` were compared and matched pinned SVD PWRCTRL.CPUPWRCTRL. This register did not yet respond. Source reset 0 was not automatically supplied merely because it is documented.

Original main bytes, PC, return values, and branches were unchanged. Existing main-reset start and explicit board fixtures remain; this does not mean full ROM/bootloader execution or physical verification.

| Observation | Value for all three normal inputs |
| --- | --- |
| Successful retention-flags reads / last value | 1 / `0x80` |
| Off requests / power cycles / controller resets | 1 / 1 / 1 |
| Power state/status / clock gate | powered-off / 0 / off |
| CQCFG/software flags and IRQ enable/status | All 0 |
| Config reads/writes | 32 / 20 |
| CQ reads/writes / IRQ-bank reads/writes | 8 / 6 and 4 / 3 |
| Prior BLE commands/responses | 59 / 60 |

The default-configuration control exactly matched prior CPU state, instruction count, all observed state, and selected events at the existing CQFLAGS block. Normal candidates preserved the prior event prefix.

## Limit revealed by a fault response

The stock 2.4 stuck-on profile continuously retains power status bit 14. Even in this case the original gated the clock and advanced to the same CPUPWRCTRL boundary. **A safe error fallback was not established.** The model kept power cycle/reset at 0 and retained CQCFG=2 and software flags=`0x80`. It did not convert failed off into successful reset. Checks for this timeout path cover explicit memory/system-control invariants; full CPU or event equivalence is not claimed.

## Implementation and verification

- `BlackwallMspi0RetentionConfig` supplies a required-argument constructor so Renode injects the required machine argument. Storage/IRQ operations use the existing shared implementation. Initial board creation rejected a missing optional machine; the constructor was made required without weakening checks. Failed main-01 artifacts were preserved.
- Candidate tool: `prepare_mspi0_retention_candidate.py`. Checks: `verify_mspi0_retention.py`, `inspect_mspi0_retention_profiles.py`.
- Performed five valid native main runs (three normal, one stuck, one default control) and five saved re-audits. Initial normal/stuck candidates failed only the semantic verdict because of bounded-capture expectations. Reports were preserved and a strict contract verified against original instructions/state was applied in separate saved audits. The CPU was not rerun for re-audit.
- Passed 24 new unit, 24 frozen, 33 existing MSPI0 queue, 33 MSPI0 config, and 33 MSPI1 CQ checks. Initial units failed due to the absent option, then passed after implementation. The MSPI1 regression reused a previously verified current-core assembly function and existing driver/board.
- Froze 87 Python dependencies and required C# inputs. Saved analysis 03/frozen 04, strengthened with HFRC2 force-release checking, have byte-identical reports and inspectors respectively. Analysis 01/02 were preserved from before the improvement. Models and execution evidence are pinned in `simulator/mspi0-retention-peer-verification-01/manifest.json`.

Proprietary main/SRAM, fixtures, and logs are outside Git. There was no physical glasses/case access, flash, OTA, persistent write, external publication, or commit.

## Next work

Investigate the CPU power and sleep/wake contract of the original caller reading CPUPWRCTRL bit 2. Distinguish completed initialization, RTOS idle, and display-task execution while advancing natural execution toward panel transfer/framebuffer. Keep full MSPI0 wake restoration and panel-state retention unverified. Do not change the overall web installation, Faceclaw CFW, and recovery boot goal or per-device approval boundaries.
