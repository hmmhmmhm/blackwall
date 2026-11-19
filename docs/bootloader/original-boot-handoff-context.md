# Stack/vector state observation at original handoff

BW539 adds only optional first-CPU-context collection to existing ExecutionObserver. Default AddPoint behavior remains; PC, active SP, MSP, PSP, CONTROL, xPSR, and VTOR are read at specified boot-reset/stock-handoff/main-reset points. CPU registers and path are not written.

## Pinned runtime API comparison

Referenced generated CortexMRegisters source had MSPCURR/PSPCURR, but the actual pinned Renode 1.17 image lacked those properties, so the first GREEN candidate did not compile. Its log remains in observer-context-green-bw539-01 and is not counted as success. Actual GetRegisters/GetProperties confirmed SP 13, Control 18, OtherSP 22, IsUsingProcessSP, and VectorTableOffset.

The actual runtime's active SP and OtherSP are read as MSP/PSP according to selection, then compared with a synthetic M55 guest switching stacks using MRS MSP/PSP and MSR CONTROL. Eighteen checks passed, including no context when unselected by default and rejection of invalid/duplicate/late collection settings. Host did not seed CONTROL/PSP for this test.

- `tools/verify_renode_observer_context.py`: synthetic ARM execution and guest mailbox/observation comparison.
- `private:simulator/observer-register-api-bw539-01/report.json`: actual pinned runtime API inventory.
- `private:simulator/observer-context-green-bw539-02/report.json`: 18 passed.
- `private:simulator/observer-context-source-bw539-01/model.patch`: observer collection only added to frozen model. Other methods in frozen observer and current root version were preserved.

Actual original boot records context at three points with the same device model/board/input. After stop, only previous/proposed/XOR VRCTRL values and stage counters are read; power model is not yet modified. Source main byte dump is checked against pinned input and immediately removed.

## Original state lineage

| Point | VTOR | Active SP | MSP | PSP | CONTROL |
| --- | --- | --- | --- | --- | --- |
| Boot reset | 410000 | 2007fb00 | 2007fb00 | 0 | 0 |
| Stock handoff | 410000 | 20022d88 | 2007fa90 | 20022d88 | 2 |
| Main reset | 438000 | 2007fb00 | 2007fa90 | 2007fb00 | 2 |

All three points are Thread mode. Original handoff stores VTOR, sets the currently selected stack with LDR.W SP, and BX to app vector. CONTROL 2 remains, so PSP actually changed. MSP is not arbitrarily changed to the vector value. This observation matches the actual SP/PSP selection fixture, completing OB05. Current progress is 5/8=62.5%; display, repeat/negative checks, and final audit remain.

Registers, instruction count, and boot globals matched bw538 exactly, and guest boot 149773 bytes/main 3700068 bytes each matched the entire original. Authoritative record: `private:simulator/original-boot-handoff-context-native-bw539-01/lineage-proof.json`.

At main stop boundary VRCTRL before/proposed were both fe1ef, XOR 0. Override step 10 complete, buck active, and MCU mode 13 remained. Next verify a contract supporting same-value rewrite of already completed configuration while retaining cold-stage order and blocking different value/width. Power model was not changed in this stage.

Two guest dumps identical to originals totaling 3849841 bytes and three fixture ELFs totaling 100164 bytes were cleaned up; owned Docker removal across five runs confirmed. Source/asm/linker, hashes, commands, actual logs, API mismatch diagnosis, and verification results remain.
