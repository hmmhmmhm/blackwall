# VRCTRL reinitialization by main after original boot

bw-0540. Completed-state rewrites in continuous stock 2.4 boot→main execution were verified. No physical access, original modification, or forced branch occurred.

Actual main ORs 0x8000/0x4000/0x2000 into VRCTRL at 0x495c96/0x495c9e/0x495ca6 respectively. Boot's 0xfe1ef already has those bits, so all three writes are identical-value writes. Compared against DFP RW fields, only a full word identical to the current value is allowed after all 10 override steps complete. Rejection of incomplete order, different values, and partial widths remains. No new power response or initialization phase is forced.

Nineteen isolated contract checks and 20 actual ARM conditions were retained. The old negative condition rejecting completed rewrites was refined to reject value-changing rewrites. RED/source/frozen model/commands/logs are in private simulator/warm-vrctrl-{red,green,arm-regression}-bw540-01.

Final native reached original main PC 0x5c1b40 at 71,980,482 instructions/7.1981 virtual seconds. It retained VRCTRL writes 16/override step 10/buck active and stopped at the next unsupported write 0x4002004c=0x1fefac. Code protection/system faults were 0 and screens 0. This is not successful normal boot or display. Overall goal remains 5/8=62.5%.

After execution, guest boot 149,773 bytes/main 3,700,068 bytes matched complete canonical copies; duplicate dumps totaling 3,849,841 bytes were cleaned up. Twenty ARM fixture ELFs totaling 668,200 bytes were also removed. Owned native container removal was confirmed. Key evidence is private simulator/original-boot-warm-vrctrl-native-bw540-01/frontier-proof.json and cleanup.json. Next analyze before/proposed inherited VDDF trim and original initialization contract.
