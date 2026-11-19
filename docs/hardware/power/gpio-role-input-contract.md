# GPIO156 Synchronization Role Input Contract

Work bw-0213. The `0x40010414` read at the [post-LittleFS block](../cpu-memory/littlefs-format-remount-ram.md) is **an input-state check of GPIO156, RD4 bit 28**. Original function names and diagnostics indicate a synchronization-role selection path. No input value had yet been supplied to Renode.

## Evidence

`inspect_gpio_role_input.py` compared pinned stock 2.4/2.3/Faceclaw38 mains, actual registers/stack, logs/reports, derived assets from existing runs, and pinned HAL/metadata, checking 49 items. HAL GPIO source commit is `61b293a49db34030c545f99101f7ebf6a3050314`, checked against SHA-256 in existing `gpio-research-01/source-report.json`.

| Location | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| GPIO read function | `0x496672` | `0x48a78a` |
| Current input read PC | `0x49668c` | `0x48a7a4` |
| Role sampling function | `0x465a6c` | `0x465d5c` |

At current pause r0=156, r3=4, r1=`0x40010414`. Caller explicitly specifies pin 156 and read mode 0. Original GPIO helper selects bank by pin/32, shifts by pin%32, then writes bit 0 to the output pointer. For this request it is RD0 base `0x40010404` +4×4, bit 28. HAL also distinguishes INPUT/OUTPUT/ENABLE read registers and applies the same shift/mask.

Pin156 config during execution was `0x93`. Metadata indicates GPIO function, input enabled, rising interrupt selected, and internal pull disabled. Configuration storage alone cannot establish external input level or electrical wiring.

## Original role decision

Original diagnostic function name is `_private_getCurrentRoleStatus`, module `sync.module.framework`.

1. Configure GPIO156 then read five times.
2. Check whether later samples differ from the first; retain an inconsistency flag if any differ.
3. Pass argument 5 to the delay function before each sample except the last. Actual time unit of this delay was not established in this analysis.
4. Return role 3 on read failure or inconsistency. Diagnostics say retrying, but this function's corresponding path returns 3 and is not described as unconditionally retrying internally.
5. Store and return role 2 for consistent high, role 1 for low.

Comparing upper-caller comparisons/branches and diagnostic strings identifies role 1 as **Master**, role 2 as **Slave**. The relative Slave-branch location differs between stock 2.4 and 2.3, so each binary's actual branch target was interpreted rather than reusing a fixed delta.

**Master/Slave correspondence to actual left/right temple remains unverified.** There is no basis to interpret it as charging, button, or wear state, so those meanings are not attached to the model. The GPIO input itself has not been physically verified.

## Isolated original GPIO helper tests

In Unicorn, the original page containing each main's GPIO read helper and literals was executed unchanged. Only GPIO registers were mapped as synthetic RAM, with normal function entry and synthetic LR return boundary. PC was not forced to branch and code was unchanged during execution.

Each main ran three INPUT/OUTPUT/ENABLE modes × 66 bank-word patterns = 198 times, 594 total. Patterns are 0/all-one, 32 single-bit, and 32 single-bit-clear; this is not an exhaustive test of 2^32 combinations. Each run confirmed one 32-bit read of the register selected by the original, normal return, and output `(word >> 28) & 1`.

For selected patterns, this shows other bank bits do not affect GPIO156 output. **It does not verify the entire role-sampling function, a new full main, debounce/IRQ, or actual pin.** OUTPUT/ENABLE modes were also checked formally, but the current full-main request is INPUT mode.

Results are outside Git in `simulator/gpio-role-input-contract-03/report.json`. Python compilation also passed.

## Next model boundary

The next experiment explicitly supplies role input low/high as separate assumptions while keeping default unknown. Supply the input signal and observe original five samples, role return, and upper branches rather than directly substituting role returns.

RD4 is a register for 32 pins. Confirming only pin156 cannot establish actual 0 for the other 31 bank bits. The model must distinguish evidence that the known current consumer reads only bit 28 from the scope of partial input. If other pins in the same bank or other read modes are used, verify access scope and diagnostics so unknown inputs are not silently supplied. IRQ changes, actual electrical level, and temple-role correspondence remain separately unknown.

## Overall state

Follow-up bw-0214 connected a [limited input adapter](gpio-role-input-model.md), confirming five low/high samples and role 1/2 returns for three originals. The unsupplied state below describes the end of this source analysis.

No Renode GPIO input model or new full-main run was added in this work. Full boot, BLE, display, and real-device installation/recovery remain incomplete; product fulfillment remains 13/29 (44.8%). No glasses access, permanent writes, or external publication occurred.
