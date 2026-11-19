# MSPI0 Queue and First DMA Submission Contract

bw-0315. Analyzed saved states of three original mains from bw314. No new native main execution or peripheral-model change occurred. **DMA descriptors are already prepared in the queue.** Allowing CQEN while treating the queue as empty would discard the actual request.

## Actual prepared queue

Stock 2.4 CMDQ handle is `0x20070498` and buffer `0x2035c460`. Stock 2.3/Faceclaw use `0x20070ec8` and `0x20376f40`, respectively. Each buffer has capacity 1,024 bytes; head is at the start and tail/next-tail at start+72. Software current index is 0, posted index 1. These are values in the SRAM handle, not substitute measurements of an uncaptured hardware index.

Each queue has the same nine address/value pairs:

| Order | Target | Value | Confirmed scope |
| --- | --- | --- | --- |
| 1 | CQPAUSE `400602b8` | `4080` | Index and HAL software flag 7 mask |
| 2 | CQPAUSE | `4000` | Change to default index mask |
| 3 | DMATARGADDR `40060108` | `20094400` | SRAM source |
| 4 | DMADEVADDR `4006010c` | `0` | Device offset |
| 5 | DMATOTCOUNT `40060110` | `25802` | 153,602 bytes |
| 6 | DMACFG `40060100` | `17` | Priority 1, M2P, HW DMA enable 3 |
| 7 | DMACFG | `0` | Disable for subsequent reset |
| 8 | CQSETCLEAR `400602b4` | `0` | No additional software-flag change |
| 9 | Encoded address `400602c1` | `1` | CURIDX address `400602c0` and update-IRQ request bit 0 |

Bit 0 of the final address is a CMDQ descriptor interrupt marker. It must not be executed as an unaligned CPU MMIO write. The original register table also contains pause-mask constants, so reading it as a contiguous array of addresses misinterprets later fields.

DMA arguments on the original caller stack are priority 1, TX direction 1, transfer count `25802`, device address 0, SRAM `20094400`, pause condition 0, and status-set-clear 0. Compared eight commands in the same order as the pinned HAL DMA CQ entry structure plus the post-block index-update command.

## Relationship between buffer and display

Read 153,602 bytes at `0x20094400` from all three images within the capture range; all were 0. The length equals the existing raw panel candidate 640×480×4 bits = 153,600 bytes plus two bytes. This is **a size match**. Whether the first two bytes are a header, whether this buffer is final scanout, and nibble order, left/right, and row direction were not yet established.

Do not count showing a blank image in the viewer as successful display output. Actual CQ fetch, DMA consumption, external transfer, and a meaningful pixel pattern must be connected.

## Original code's enable return and subsequent wait

Executed original ARM in Unicorn M7 from saved native PC, GPR, and full SRAM. If an explicit CQCFG-write fixture accepts value 3, the original sets bit 25 in the CMDQ handle and returns 0. Two stop boundaries were checked:

1. The CQ-enable function's actual LR return point.
2. Immediately before the upper DMA caller's semaphore-wait call. DMA return value is passed as 0 and wait argument is 3000. This check alone does not establish that its unit is milliseconds.

Three images × two boundaries × MMIO-callback/ordinary-memory controls = 12 ARM executions. Each full PC trace, SRAM, WORK, general registers, XPSR, and PRIMASK matched its control. The CPU enable path did not change the prepared descriptors. This is **not evidence that the actual queue executed descriptors or DMA completed**.

In initial exploration, continuing beyond the wait function caused a passive M7 RTOS-list path to reach the 3,000-instruction limit. Do not treat isolated execution without scheduler/interrupts as natural M55 boot progress. The final checker stops immediately before the wait call without bypassing it or forcing a return.

## Conditions remaining before modeling

The pinned SDK describes setting SWFLAG7 to unpause and clearing it to pause. The SVD CQMASK description specifies matching conditions for all designated events. Do not implement this as a simple `flags & mask != 0` condition. Verify software-flag polarity, index conditions, and actual pause timing together.

Also establish hardware serialization/wait conditions between DMA start and the immediately following disable descriptor. Unconditionally completing all nine after one timer tick would skip the original argument's 153,602-byte transfer and DMA/CQ IRQ boundaries. DMA enable 3 also includes automatic instruction/address generation in the SVD. Its relationship to DEV0INSTR/configuration and wire format remains to be checked.

Next use these nine actual descriptors to combine CQ fetch, pause, DMA lifetime, index update/IRQ, and failure conditions. Keep unconfirmed behavior as explicit hypotheses and distinguish virtual transfer capture from actual external-slave effects. Then verify panel-packet/framebuffer integration.

## Evidence and preservation

- Tool: `tools/inspect_mspi0_cq_submit.py`.
- Private analysis `mspi0-cq-submit-source-03` and frozen `mspi0-cq-submit-frozen-01`: byte-identical report/inspector. Froze 96 Python dependencies.
- `mspi0-cq-submit-verification-01/manifest.json`: hashes of inputs/outputs, SDK/SVD, tools, and nine existing models. All existing models were unchanged.
- Compared SHA for `am_hal_cmdq.c/h`, `am_hal_mspi.c/h`, and header/SVD from pinned HAL commit `61b293a49db34030c545f99101f7ebf6a3050314`. Do not generalize that the actual firmware's entire ABI matches.
- Preserved the first analysis failure caused by omitting pause constants from the register table and initial disassembly at the wrong halfword boundary in private research. Final checks use actual return/call boundaries and original table fields.

Overall criteria were 13/29 = 44.8%, scope v2. There was no physical glasses/case access, flash, OTA, persistent write, commit, or external publication. Full boot, integrated display, and physical recovery remained incomplete.
