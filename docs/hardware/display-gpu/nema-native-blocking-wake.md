# Original blocking wait and delayed GPU IRQ wake

Work `bw-0267`. The immediate-completion path of [original PendSV resumption](nema-native-pendsv-resume.md) was extended to actual waiter registration, removal, and consumption.

In stock 2.4, stock 2.3, and Faceclaw 38, **original wait waiter registration → removal from ready list → actual IRQ28 → original give releasing wait → PendSV restoration → original take consuming semaphore → wait return** was verified. This is not natural full-main UI or physical hardware verification.

## Explicit test event

`--deferred-completion` was added to existing `--kernel-context` execution. After processing framebuffer and footer, diagnostic GPU does not immediately raise completion IRQ. It releases completion only at original PendSV entry when all actual RAM conditions hold:

- Semaphore receiver waiters=1, messages=0.
- Current task event-list container matches semaphore receiver list.
- Current task removed from previous ready list, corresponding ready count=0.
- Scheduler suspended counter=0.

Observation callback reads this state and changes only GPU IRQ line. It does not write kernel RAM, PC, or returns. This is an **explicit test condition where completion arrives after wait registration**, not a time model imitating physical GPU latency, clock, or power. SysTick remains disabled as in existing fixture.

`--block-boundary-control` does not release completion under the same wait conditions and stops at `semaphore-blocked`. This is not a timeout wait or full indefinite-wait verification.

## Final M55 results

| Item | Result in all three images |
| --- | --- |
| Actual waiter / messages before completion | `1 / 0` |
| Ready count / scheduler suspended before completion | `0 / 0` |
| Actual IRQ28 / CLID reads / ack | `1 / 2 / 1` |
| Original scheduler selection | `ble_wsf → manager → ble_wsf` |
| PendSV / selector / port return | Twice each |
| Waiter / event container after completion | `0 / 0` |
| Semaphore count after completion | `0` — consumed by original take |
| Original wait return | 0, descriptor ID cleared to `0xffffffff` |
| Caller completion markers | All 1..7 recorded |
| Final CPU | Thread/PSP, existing PSP/MSP restored, CFSR/HFSR=0 |
| Actual guest framebuffer | Identical to previously verified A glyph bytes |

After first selector chose manager, IRQ returned original waiter to ready list; second selector chose ble_wsf. Actual selected TCBs were recorded. Meaningful progress of manager business code was not verified.

Manager's original saved frame and stack range were checked in each image's full RAM/task graph. Extra permitted writes are limited to declared alternate task stack, TCB saved-SP, related ready/wait lists and semaphore structure, and verified kernel words. Both task stack canaries remained; System SRAM changes were confined to declared alternate stack.

Without completion, control returned through submit but retained waiter=1, messages=0, last ID=`0xffffffff`, and wait marker 7=0. No IRQ, ack, or CLID read occurred. Separate immediate-completion regression confirmed one PendSV, semaphore count=1, and completed wait return as before.

## RAM contract first confirmed with original functions

`tools/inspect_nema_blocking_wait.py` ran original wait/give and task selector in a separate Unicorn M7 function fixture. ICSR is passive memory in that part, not actual NVIC execution.

Initially take was called directly and give executed in same TCB state before switching. Wait was released but `higher-woken=0`; expecting it always to be 1 was wrong. A contract matching actual native path was then built: **original wait wrapper → first selector (manager) → give → second selector (ble_wsf)**. Here higher-woken=1. Earlier failed expectation and result were preserved.

Final RAM diff did not expose every transient critical-nesting and ready-list-index write. For exact wait/give inputs, observer-on/off runs had identical full PC paths, SRAM, WORK, and general registers, and write addresses were collected. Selector round-robin index can return to its final original value, so the corresponding ready-list structure range from source task graph was used. This verification is limited to wait/give for that input; it is not expanded to previous memset observer issue or general noninterference of other functions.

## Saved material and verification

Under `simulator/` outside Git:

- `nema-blocking-transactions-01`, `-02`: pre-switch higher-woken expectation failure; RAM/failure state preserved in `-02`.
- `nema-blocking-transactions-03`: initial take/give contract.
- `nema-blocking-transactions-04`: original wait wrapper and observer on/off control.
- **`nema-blocking-transactions-05`**: final RAM contract including two selectors.
- `nema-deferred-block-control-01`: failed due to omitted transient critical-nesting writes.
- `nema-deferred-block-control-02`: wait-condition confirmation, initial control.
- `nema-deferred-wake-01`, `-02`: failed due to omitted transient index write range in alternate ready list; corrected from original alternate-task structure, stack, and list.
- **`nema-deferred-wake-03/stock24`**, **`nema-deferred-wake-peers-01/{stock23,cfw}`**: final successful wakes across three.
- **`nema-deferred-block-control-03/stock24`**, **`nema-deferred-immediate-regression-01/stock24`**: final control/regression.
- **`nema-deferred-wake-verification-01`**: final five saved executions passed **240 checks** using `tools/audit_nema_blocking_wake.py`. Checks include actual witness, NVIC, TCB selection, RAM bounds, stack canaries, original pixels, return markers, and controls. Audited without native rerun. Fourteen M7 analysis dependency modules and hashes/package versions plus unit log preserved.

Of nine native original-function runs, five final adopted and four development runs are distinct. Python compile and 17 existing native-contract unit tests passed. Failure evidence was not retroactively altered.

## Remaining overall goal

This stage is the blocking path of a configured PSP caller. Existing main starting from stock reset still has SPI/display initialization and external font-bank boundaries; integrated 576×288 screen remains incomplete. Next recheck conditions for connecting original main display-call path to this GPU/completion model. Do not keep adding function-fixture wait/resume tests as a substitute for full-screen goal.

Faceclaw CFW for web installation, recovery boot, and preparation for stock restoration remain overall goals. Product conditions **13/29=44.8%, scope v2**. No physical glasses/case access, firmware writes, or external publication.
