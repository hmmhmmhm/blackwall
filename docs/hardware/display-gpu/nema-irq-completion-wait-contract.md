# Original GPU IRQ, completion ID, and semaphore wait contract

bw-0261. The original IRQ function path publishing stable CLID and invoking actual semaphore give, and original wait's complete/incomplete branches, were confirmed. **Function tests use an auxiliary Unicorn M7 engine; actual NVIC IRQ delivery, M55 scheduler, and completion connection to earlier live GPU model are not yet present.** No success return or semaphore mock was inserted.

## State captured from original main

`nema-irq-semaphore-candidate.json` reran three pinned original mains to the existing boundary. Board, peripheral models, branches, and execution observer were unchanged; handle, callback, completion ID, and 96-byte queue were read only after stopping. CPU, instruction count, all observations/events exactly matched baseline and schema2 semantic checks passed.

| Item | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| IRQ28 vector | `0x560eaf` | `0x52ff9b` |
| Actual IRQ core | `0x560e50` | `0x52ff3c` |
| Completion ID storage word | `0x20005e3c` | `0x20003c8c` |
| Semaphore handle slot | `0x20077384` | `0x20077bd8` |
| Actual queue object | `0x200079b0` | `0x20005658` |

All three queues had token 0, capacity 1, item size 0, zero receiving waiters, callback 0, and completion ID `-1`. Actual objects created by emulated main were restored rather than assuming zero fill in existing partial SRAM represented initialized state. The same state is not assumed at other times or physically.

## Original IRQ function sequence

Original vector wrapper and core executed unchanged. Registers are passive MMIO; CLID read sequences are explicit test inputs.

1. Read GPU CLID offset `0x148`.
2. Write 0 to GPU interrupt offset `0xf8` and call NVIC IRQ28 pending-clear code.
3. Read CLID again; if different from previous value, repeat from step 2.
4. After two consecutive identical CLIDs, store in original global completion ID.
5. Execute original semaphore-give-equivalent function with restored actual queue as argument.
6. If higher-priority-woken stack word is nonzero, write PendSV request bit in ICSR. Call callback if present; actual state here is NULL.

This corresponds to stabilization/notification order in pinned [Apollo510 Nema HAL](https://github.com/AmbiqMicro/lv_port_ambiq/blob/be2dfdd522f7897c819c422d319d1ee3949fab95/lvgl_ambiq_porting/NemaGFX_hal/apollo510_nemagfx/nema_hal.c). It does not restore exact SDK/FreeRTOS version or removed firmware symbol names.

## Observed data flow

Per firmware, stable 8,8 → 9→9, 8→9→10→10, woken seeds 1/`0xa5a5a5a5`, continuously varying CLID, and code-observer off were compared. Of 21 canonical IRQ function entries, 18 actually returned and executed actual give, changing token 0→1. Three stopped at CLID sample-budget boundary.

| Input | Completion ID | Semaphore token | IRQ function return |
| --- | ---: | ---: | --- |
| 8,8 | 8 | 1 | Normal |
| 8,9,9 | 9 | 1 | Normal |
| 8,9,10,10 | 10 | 1 | Normal |
| 8,9,10 then no sample | -1 retained | 0 retained | Sample guard stop |

Unstable input is not an instruction timeout counted as success. Last original MMIO read requested a sample beyond declared budget and stopped. Saved results confirm publish/give did not execute.

For each of 18 actual returns, original list wait was also tested. For published ID and smaller IDs, original returned 0 and cleared list ID to `-1` (36 runs). Larger ID reached original semaphore-wait function entry (18 runs). Observation ended there; blocking path, successful return, and timeout of semaphore take were not implemented in its place.

Give is not a fake function. Original function updated captured queue message count and executed/restored BASEPRI critical section using original instructions. Analyzer rejects before execution if callback, waiters, or item size falls outside this restored scope.

## Why PendSV cannot be ignored

Original core pushes R3 to create a local word and does not separately initialize it to 0. On this waiter-free queue, original give did not change that word. Consequently entry R3=0 produced no PendSV request write; 1/`0xa5a5a5a5` made original code write `0x10000000` to ICSR. This reproduced without changing callback, give result, or source branch.

Pinned vendor HAL likewise passes a local higher-priority-woken variable to give without initialization. FreeRTOS [official API reference 10.0](https://www.freertos.org/media/2018/FreeRTOS_Reference_Manual_V10.0.0.pdf) describes how this argument is set under wake conditions. That document is not evidence of G2 kernel version.

This is not expanded into actual-device failure or general scheduler failure. Actual NVIC exception entry, priorities, stack frames, and task switches are absent. ICSR/ICPR are passive words, so observation is a **request write**, not PendSV execution. Nevertheless forcing R3=0 or deleting PendSV request to pass future IRQ integration would not preserve original path.

Original PendSV saves PSP/PSPLIM and conditional FPU context and calls task-selection path. This was not executed. Static addresses requiring next capture:

| Next state | Stock 2.4 | Stock 2.3 / Faceclaw38 |
| --- | --- | --- |
| Current TCB slot | `0x2007764c` | `0x20077e38` |
| Scheduler query input slots | `0x20077668`, `0x20077684` | `0x20077e54`, `0x20077e70` |
| PendSV entry | `0x60bb70` | `0x61bac0` |

Current values at these addresses are **not collected**. Do not interpret zero fill of existing partial snapshot as actual kernel state. Before implementing GPU CLID-only changes or successful wait returns, identify actual main RTOS/TCB and PSP state.

## Evidence and limits

- Three native main read-only captures: `simulator/nema-irq-semaphore-main-01`.
- Original ARM function contract: `nema-irq-contract-02/report.json`, pinned inspector and static instruction records.
- 180 saved-audit checks: `nema-irq-contract-verification-01/audit.py/report.json/source-pins.json`.
- Source: `tools/inspect_nema_irq_contract.py`, `tools/nema-irq-semaphore-candidate.json`.

With code observer off, SRAM, stack, and ICSR/ICPR results immediately after IRQ matched. No memory-write observer was used. Read guard permits only captured/declared ranges; original IRQ changed SRAM only at completion ID word and queue message count.

After initial contract01, checks for preservation of other passive MMIO addresses and static PendSV/scheduler addresses were added for 02. Subsequent stronger explicit sample-budget checks were reaudited against saved unstable results. Native main was not repeated for the same reason. Python compile and 180 audits passed; container exit confirmed.

Next read original main IRQ/RTOS initialization state, TCB, PSP/PSPLIM to establish prerequisites and scheduler boundary for actual M55 IRQ delivery. Remaining full-main SPI, external font-bank, 576×288 display, and web installation/recovery conditions remain.

**Product 13/29=44.8%, scope v2.** No actual glasses/case access, RAM execution, OTA, or persistent writes.
