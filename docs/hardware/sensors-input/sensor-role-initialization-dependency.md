# Role and mode dependencies in sensor initialization

bw466. Two premises for bypassing the normal GAF bottleneck were examined. **Further error-input variants duplicate existing tests, and the current board already has the Master profile. Mode 3's zero configuration is not evidence of GAF disable.** Neither model nor original main was changed and no new native run was performed. Overall 10/16=62.5%.

## Reuse of existing error tests

[WHOAMI mismatch](imu-identity-failure-native.md) and [initial indirect profile](imu-initial-indirect-profile.md) ultimately reached the same GAF service in prior runs of three originals. [Actual IOM NAK](../power/iom4-nak-error-recovery.md) also stopped at an unsupported indirect transaction without reaching upper initialization return; the record already says not to multiply identical error variants. They were not rerun as new approaches. Unspecified ready or return manipulation is not an alternative.

## Role already selected by the current profile

The three actual original boards in bw465 use `gpio_role_input level:0`, budget 5. Existing [GPIO156 contract](../power/gpio-role-input-contract.md) confirmed low → role 1/Master, high → role 2/Slave. The role getter in actual saved snapshots also returned 1. Do not rename Master/Slave as unverified physical left/right.

The sensor task's role-based configuration function stores mode 3 for role 1 and mode 2 for role 2. Executing it as actual ARM in existing role-1 state of all three originals confirmed mode 3 and SRAM preservation. No other role was written by the host or changed through a new board run.

## Mode 3 zero does not mean disable

The wrapper's mode configuration table has five 16-byte rows. Modes 0/1/2/4 have period 10000; the mode 3 row is all zero. But the actual configuration helper handles only periods 1000/2500/5000/10000/20000/40000 and returns -1 for 0.

In 15 ARM runs (three originals × five actual configuration rows), mode 3 returned -1 with full SRAM unchanged; the others returned 0. Snapshot GAF enable byte remained 1 in all cases. The table's zero therefore cannot be interpreted as sensor off, a mode not requiring GAF, or completed computation.

Three additional wrapper runs isolated only power/reset leaves as ABIs and executed the actual mode 3 configuration helper. Original code continued to actual initializer entry without checking -1. Observation stopped before initializer entry; completed initialization was not simulated. This is wrapper control flow for this fixture, not general proof that GAF must run in every power/role state.

## Task dispatch relationship

Pointers to two handlers were found in the ten-row dispatch table in saved initialization RAM. Failure to find a complete pointer word in flash was not used as evidence that the function is unused. The original dispatcher actually calls indirectly type 1 → mode command handler, type 2 → FIFO consumer wrapper.

Six independent runs (three originals × type 1/2) confirmed each target. Type 1 stopped before handler entry; type 2 returned without actual FIFO consumption under snapshot gate 0. This is not a natural main test changing host queue or task flags.

The total 27 runs comprise role configuration 3 + mode configuration 15 + wrapper boundary 3 + dispatch 6. Role, gate, and original branches were not changed by the host. This remains isolated M7 testing using some wrapper leaf ABIs and synthetic messages.

## Next choice

Do not retest the same WHOAMI/NAK, timeout, role changes, or mode 3 zero row as new normal-boot solutions. Normal GAF still needs an execution specification/exact code and ISA or independent calculated results and scope of effects. Do not judge functionality as normal E05/E12 without resolving those conditions.

Independent device work remains: implement the original FIFO read contracts of bw462–463 as actual FIFO register/input lifetime in the virtual IMU peer. It can be combined with the GPIO38 model, but retains the limitation that natural sample consumption does not occur at existing gate 0. This does not replace GAF or change completion criteria for normal natural rendering.

Evidence: `simulator/sensor-role-dependency-01/{probe.py,report.json,manifest.json}` outside Git. Source pins are verified bundle/main, existing snapshot, and GPIO role/bw465 board. No new native run, model changes, physical access, subagents, or external publication.
