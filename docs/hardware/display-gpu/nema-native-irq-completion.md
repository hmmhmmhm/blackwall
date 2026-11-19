# Connecting original drawing to actual NVIC IRQ28 completion handling

Work `bw-0264`, following [live drawing](nema-live-draw-framebuffer.md) and [original IRQ contract](nema-irq-completion-wait-contract.md).

Across stock 2.4, stock 2.3, and Faceclaw 38, **original draw → diagnostic GPU framebuffer → actual NVIC IRQ28 → original IRQ completion ID/semaphore update → PendSV entry boundary** was connected. This is not natural full-main UI path, resumption after RTOS wait release, or physical GPU verification.

## Configuration and explicit assumptions

`--completion-irq` was added to existing `tools/run_nema_submission_m55.py`. Default remains diagnostic GPU without IRQ. New option requires `--reference-gpu --live-draw`.

Execution begins in a synthetic ARM caller, not main running from original reset. Caller invokes original list bind, destination, clip, letter, unbind, and submit. Command buffer begins A5 poison/used=0; original draw functions create 42 words. No expected framebuffer is placed in guest.

Diagnostic GPU handles only existing binary white A4 → black L8 64×32 profile. It validates commands and writes guest framebuffer on first doorbell; after validating second doorbell footer it provides CLID=8 and IRQ line. Actual connection is `GPU.IRQ → NVIC@28 → CPU@0`; model does not call IRQ function directly. VTOR is original table `0x438000`, priority test value `0x40`. Completion timing and immediately stable CLID are diagnostic assumptions, not hardware timing measurements.

`tools/nema_native_irq.py` verifies/restores semaphore handle, callback, 96-byte queue, and last ID previously captured from original main. This is a copy of actually captured state with capacity=1, messages=0, receiver waiters=0, callback=null. Full scheduler/TCB is not restored.

Thread uses synthetic MSP stack. Inactive PSP=`0x2100d000` distinguishes stop scope, not a prepared task stack. Original code unchanged. Host PC setting is used only for first synthetic caller entry; no forced branches between functions, direct IRQ calls, or fake successful returns.

## Final three-image results

| Item | Result in all three images |
| --- | --- |
| Five original draw returns | markers 1,2,3,4,5 |
| Actual guest framebuffer | Matches previously verified A bytes |
| Actual IRQ28 | Once, IPSR=44 |
| R3 at IRQ entry | `0x2100b000`, original submit ring pointer |
| Original CLID stabilization | Two reads, both ID 8 |
| Original GPU IRQ ack | Once, IRQ line released |
| Original last ID / semaphore count | `0xffffffff → 8` / `0 → 1` |
| Actual PendSV | Once, stopped at `rtos-context-required` boundary |
| CFSR / HFSR | `0 / 0` |

Full SRAM comparison showed changes only to **two words**, last ID and semaphore count. Original IRQ and give functions wrote them directly; host did not substitute completion values. Exception frame and function stack are written in synthetic WORK.

Original IRQ local woken value retained entry R3, and give with no receiver did not initialize it to 0. As in earlier contract, nonzero caused original PendSV request. R3 was not adjusted to 0 and request not discarded to pass.

Submit is preempted by IRQ, so marker 6 is 0. Even though ring cursor, queued ID, and list ID were already updated, submit return is not counted complete. Original PendSV's first `MRS r0, PSP` was confirmed not executed because R0 remained entry value and did not become distinguishing PSP. Task selection/save/restore and semaphore blocking→resume remain unconnected.

## Controls and failure records

`--irq-disabled` omits only NVIC IRQ28 enable in same profile. Framebuffer and GPU completion line appear, but IRQ, CLID reads, ack, and PendSV are 0. Last ID remains `0xffffffff`, semaphore 0, and all six original calls return. This controls that publication was not caused by host SRAM modification.

Default IRQ-disabled profile was rerun with final model/guard. All WORK matched prior live draw and existing return/register/buffer/pixel checks passed.

First PC-hook stop result confirmed publication but could not prove the first PendSV instruction unexecuted. Strengthened test throwing CpuAbortException in PC AddHook callback failed with **host exit 133**. It was moved to block-begin guard. PSP=0 test could not distinguish entry R0 from MRS result and failed strengthened check. Stop scope was verified in final three using nonzero inactive PSP. Earlier failed captures or success judgments were not changed.

## Saved evidence

Under `simulator/` outside Git:

- `nema-native-irq-m55-01`: original store operand check failed before native; new path after inspector correction.
- `nema-native-irq-m55-02`, `nema-native-irq-peers-01`: initial three-image publication connection and PC-hook stop limit.
- `nema-native-irq-disabled-01`, `nema-native-irq-default-regression-01`: initial control/regression.
- `nema-native-irq-strict-stop-01`: exit 133 failure from PC-hook exception.
- `nema-native-irq-block-stop-01`: strengthened check failure with PSP=0.
- **`nema-native-irq-final-01/{stock24,stock23,cfw}`**: final three passed.
- **`nema-native-irq-disabled-02/stock24`**, **`nema-native-irq-default-regression-02/stock24`**: final control/regression passed.
- **`nema-native-irq-verification-01`**: final five saved runs audited with `tools/audit_nema_native_irq.py`, **258 checks passed**. Inputs, logs, original vector, guest bytes, SRAM differences, and controls checked without native rerun.

Distinguish 12 native runs (five final, seven development) and one pre-native input-check failure. New runs add the options above to existing runner and always specify new private output.

Next obtain original kernel-state collection/restoration scope to connect PendSV/task selection and wait resumption. Synthetic-fixture progress does not replace full-main screen or web installation/recovery completion. Overall completion **13/29=44.8%**. No glasses/case access, firmware writes, or external publication.
