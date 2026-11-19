# IOM Command Queue Contract

bw-0120. Static investigation comparing pinned DFP/HAL with actual stock 2.4 register table and initialization instructions. This is not physical verification or a CQ execution result.

## Confirmed source-supported behavior

- A HAL entry consists of a 32-bit address and 32-bit value. Entry address bit 0 requests CQUPD.
- CQADDR is the next fetch address; if CQ itself writes CQADDR, it changes the next pair's address.
- CQCURIDX is a block index explicitly written by a CQ entry, not automatically incremented per pair.
- It stops when equal to CQENDIDX and CQPEN bit 15 is set. Software flags 0..7 are also pause inputs.
- CQTIP is 1 even while enabled/paused. Disabling clears CQSTAT bits.
- Upper 16 bits of CQFLAGS are pause interrupt masks, distinct from INTEN IOM cause bit 12=CQPAUSED and bit 13=CQUPD. NVIC remains 6+module; module 4 is 10.

`analyze_iom_cq_contract.py` verifies pinned stock 2.4 raw SHA, SVD/header, and new HAL cmdq c/h hashes. Ten words of the actual stock register table's module 4 record matched DFP addresses/masks. Actual initialization includes instructions requesting CUR/END=0, pause IDXEQ, CQADDR=buffer, and CQCFG priority/disabled. The complete public HAL ABI is not assumed identical to actual G2.

The pinned Renode tree has no completed Ambiq CQ backend; IOM CQ fields are placeholders. Implement an MMIO CQ component fetching addresses/data separately from the existing polling backend. Do not replace original HAL functions with host functions.

## Implementation scope and unknowns

The initial component handles word-aligned eight-byte fetches from explicit SRAM, own-IOM strict MMIO destinations, software/index pause/resume, self-jump/self-disable, and CQUPD. It is a functional model evaluating pause before first fetch, not reproduction of pipeline prefetch or physical timing. Relationships for flags 8..14 depending on external GPIO/BLE/MSPI/IOM inputs are unknown. Selection of these pause inputs and full CQFLAGS reads are blocked, exposing only known software/index flags in diagnostics. Simultaneous set/toggle/clear requests for the same bit are rejected because precedence is unknown.

Fetch checks SRAM end and overflow, then alignment, own-IOM range, and register permissions after clearing destination address bit 0. Completion of a previous pair is distinguished from stopping on a subsequent unsupported pair. A 4096-pair activation limit prevents infinite host loops; it is a model limit, not physical CQERR behavior. DMAEN remains blocked until separate implementation/verification. DMATRIGEN configuration storage is performed only with DMAEN 0 and does not claim actual trigger/DMA transfer implementation.

## Evidence

HAL sources are `am_hal_cmdq.c/.h` from `zephyrproject-rtos/hal_ambiq` commit `61b293a49db34030c545f99101f7ebf6a3050314`. Git blob SHA1 was verified and SHA256/originals preserved outside Git. Renode tree was checked at infrastructure commit `066a7f13c052215632d469c995c89aea37c573b1`. Evidence is `private:simulator/iom-cq-contract-01/report.json`, `iom-cq-research-01/download.json`, and `iom-cq-research-01/renode-ambiq-tree.json`.

Independent review in the same GPT-6 family found no additional significant contradiction. Its recommendation to verify labels for atomic preflight, self-jump/reentrancy, eight-byte boundaries, initial pause, and budget limits in actual code is incorporated. Other model families and archived transcript comparison were not performed. Full CQ/DMA and boot/display remain incomplete.
