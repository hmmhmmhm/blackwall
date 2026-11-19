# IOM Functional CQ Model

bw-0121. A command-queue component is implemented behind MMIO without changing original firmware functions or branches. This does not complete full CQ/DMA, boot/display, or physical verification.

## Executed behavior

`BlackwallIomCommandQueue` reads word-aligned eight-byte address/data pairs from virtual SRAM and writes to that IOM's strict register handler. CURIDX changes only when an entry explicitly writes it. Software/index pause/resume, CQADDR self-jump, and CQCFG self-disable are handled. CQTIP remains 1 while paused and status is 0 when disabled. The 4096-pair activation limit is a model stop to prevent infinite host loops, not a simulated actual CQERR.

Out-of-range source/destination, destination bit 1, and read-only/unsupported registers are blocked. Destination bit 0 is removed only as the CQUPD marker. Address does not advance on an unsupported pair; previously completed pairs remain. This functional sequence evaluates initial pause before first fetch and does not reproduce pipeline timing. IOM cause bit 12=CQPAUSED is set when the intersection of pause selection, flags, and IRQ mask newly activates. Bit 13=CQUPD is set after a marked pair completes. Module 4 NVIC is 10.

DMATRIGEN stores configuration only with DMAEN 0. DMAEN requests continue to be rejected from both CPU and CQ. Actual trigger-status behavior is unimplemented, so status queries while a trigger is armed are blocked too.

## Unknown external inputs by default and explicit assumptions

GPIO/MSPI/IOM/BLE inputs are unknown by default. Full CQFLAGS reads and pause/IRQ selection of unknown flags are blocked. Actual stock code stores full CQFLAGS in a state structure during IOM2 power-save, so initial default execution of the new model stopped at PC 0x581e82. This differs from the old placeholder's 0 response.

`--iom-cq-input-levels 0` declares a **virtual input assumption**. Five bits are selected MSPI0, MSPI1, GPIO, IOM, and BLE input levels in order. Each pin's XOR/XNOR with SWFLAG0..4 is calculated according to pinned DFP. MSPIFLGSEL other than selector 0 remains unsupported. Model pin 0 does not mean its relationship with actual signals is established. Constant-signal assumptions are distinct from actual input wiring/timing.

For example, with SWFLAGS 0 and CUR=END, CQFLAGS low is 0x8c00 for vector 0 and 0xf300 for vector 31. The full flag word is not fixed to 0. CQFLAGS low 16 is read-only and ignores writes, while upper 16 IRQ mask updates. Unknown mask 0 in mock mode means values were assumed; physical_flags_verified is always false. Default unknown mode was not relaxed.

## Verification and failure record

- red01 failed because the existing wrapper lacked CommandQueue; native log was preserved.
- After the first 67 conditions, independent review found PauseEnable missing from IRQ conditions. unit03 passed 79 conditions including separate pause/IRQ mask regression.
- Checks include actual fetch of the last eight source bytes, blocking the next out-of-range fetch, four-byte alignment, destination bit 1, self-address/disable, partial commit, index wrap, budget, and blocking DMAEN from both CPU and CQ.
- These checks use host-written synthetic SRAM entries, separate from original firmware runs. NVIC pending tests are not generalized to actual CPU ISR execution.
- Seven native fixtures with explicit vectors 0/1/2/4/8/16/31 verified 43 conditions for pin positions, SWFLAG connections, and XOR/XNOR. They do not verify actual GPIO/sensors.
- Adapter 82/shared 33 passed. Sixteen CQ placeholder rejection checks moved from existing adapter 98 to functional CQ checks; the small assertion-count change does not represent product progress.
- The first mock harness string edit failed with Python SyntaxError before native startup. Launcher records were preserved and execution followed correction.

## Final original runs and audit

Under explicit input 0 profile in `iom-cq-main-comparison-01`, stock 2.3, 2.4, and Faceclaw38 all passed IOM4 CQ initialization/power-off and stopped at IOM5 power request (DEVPWREN=0x40). PC is 0x494d78 for stock 2.4 and 0x488e90 for stock 2.3/CFW. IOM4 had 13 writes/21 reads. Actual CQ pairs 0 and I²C commands 0; this is not treated as original-firmware CQ transfer success. Two IOM2/4 power-readiness failure conditions were separately run and each blocked an unpowered configuration write.

Current source's default unknown profile was also rerun in `iom-cq-default-strict-stock24-01`. CQFLAGS read (0x40052234) at PC 0x581e82 stops as cq-external-flags-unknown. Mock-input progress and default unknown state are preserved separately.

`verify_iom_evidence.py` compared 21 sources, combined C#, harness originals, host source, raw logs/reports, original main SHA/vector, stock 2.3↔CFW execution scripts, and 36 DFP masks. Unchanged UART core 117/shared 28 evidence was reused after confirming source identity. `iom-cq-verification-03/report.json` preserves CQ 79, mock 43, adapter 82/shared 33, five originals, and default-strict evidence.

Audit01 failed because it retained a condition that r5 was an IOM4 handle at the previous stop. The new stop was a power helper with r5=0; module 4/mode 1/NBptr/length at pinned handle 0x20040b28 still matched. The checker corrected register context for the changed endpoint; native was not rerun to make it match. Failure summary is preserved in `iom-cq-verification-01/audit-failure.json`.

Independent review in the same GPT-6 family found no additional significant issue. Other model-family and archived transcript comparison were not performed. Next are IOM5/7 initialization connection and implementation of DMA SRAM/FIFO/trigger/completion contracts. Physical input/timing, full boot/display, and installation verification remain incomplete; product progress remains 13/29.
