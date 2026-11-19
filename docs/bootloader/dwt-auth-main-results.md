# DWT/watchdog and same-board authentication completion

2026-11-17 · bw-0579. **BV05 complete, overall 11/12=91.7%.** Remaining BV06 is same-board recovery command completion→main and original comparison. This task confirmed normal, error, and timeout/retry authentication and main entry from original reset/worker on the same supported virtual board. It does not certify physical safety or device compatibility.

## Explicit virtual environment

Pinned current 2.3 patch SHA `7010d103…e55a7e`, same-bundle main `69f9ef63…13b9c`, synthetic chip 21/trim 1, and existing B0 power/context-qualified retention were used. Host does not change CPU/firmware/RAM/IRQ/branches.

- Native `Miscellaneous.DWT` in pinned runtime was connected to board `0xe0001000`. Type, reset, enable/disable, accumulation, and 32-bit wrap were checked in **10 tests** on the actual engine. Frequency 10 MHz is an explicit functional assumption matched to CPU 10 MIPS. It is a virtual-clock counter, not a claim of actual M55 cycle accuracy. Source commit `cd4b002aac2398994c4a61a34a8b31b5700facf2`, DWT.cs SHA `646fe41e…a0c216`.
- PMIC timer defaults to ConfigKnown/TargetKnown=false. Adding only explicit zero mocks for the two middle bytes still stopped unknown config/target reads; that result was retained.
- Supported fixture is **virtual initial hardware state** supplying four transactions, config 0a, target 003c00, strobe, and start, to the PMIC model API before the first guest instruction. Initial CPU instruction 0, timer writes 4, kick 0 were collected. Mismatch control target is 003c01. This is not an observation that actual hardware had this initial state.
- Existing `recoveryReadHoleMock=0` fills middle bytes 0706/0707. Original guard's `lo & 0xff0000ff` excludes those bytes. An independent mask check gave the same decision for all 65,536 combinations. Actual values read from those registers and electrical behavior were not verified. Default unknown state was not promoted to supported/safe.

## Actual original execution controls

| Scenario | Wire authentication | Watchdog | Original main |
| --- | --- | --- | --- |
| Normal HOLD→OKAY→CONT/RLSD | Complete | kick 1, original return 1 | Entered |
| Invalid HMAC | Rejected, live claim 0 | Calls 0, kick 0 | Entered |
| No input | No authentication | Calls 0, kick 0 | Entered |
| Valid retry after invalid HMAC | Complete | kick 1, return 1 | Entered |
| Valid retry after partial 8 bytes/128-tick-or-longer timeout | Complete | kick 1, return 1 | Entered |
| Normal authentication, timer target mismatch | Complete | Original return 0, kick 0 | Entered |

Actual UART2 consumption FNV64, complete HELO/OKAY/RLSD bytes and HMAC/checksum, live held/claimed, and receive-entry counts were independently compared for each input. The same model/board/observation was used, changing only initial PMIC target or UART input. All six final natives had unchanged guest boot/main hashes, and CPU fault, guard, memory policy, missed observation, unregistered device access, and engine abort 0. Runner stops after main reset hit, so this does not verify full main boot/display.

Normal feed performed three original IOM7 commands and changed PMIC kick 0→1. Mismatch returned 0 after two commands without a kick. Both cleaned up IOM7 power and restored DWT CTRL to 0 before entering main. No separate UART IRQ exception probe was attached, so its counter 0 is not evidence that no actual IRQ occurred.

After main entry, old worker session memory may be reused by main initialization. Authentication rejection/claim history is not inferred from final session 0 alone; live snapshots and wire responses during authentication were used.

## Verification, failures, and cleanup

Frozen audit **104 checks** and `/tmp` rerun 104 passed. DWT native unit 10, runner input/classification 4, and upstream runner 5 passed. Apart from previously unregistered DWT, native02 was diagnostic of PMIC unknown read and native03 confirmed read-hole option alone was insufficient. Neither is included as success.

First native01 incorrectly specified PMIC node as sysbus.pointerProbe, causing final exporter failure. It was corrected to actual sysbus.iom7.pointerProbe path and partial results retained diagnostically. After source and actual `timer-read-unknown` confirmed initial PMIC config/target unknown, two separate explicit initial-state fixtures were compared. Model conditions were not hidden or historical reports changed to success.

Ten owned native jobs terminated and current container absence confirmed. Thirty-four duplicate firmware files totaling **69,399,916 bytes** were cleaned up. Key source, hashes, logs, model, failure diagnostics, and reproducible audit remain. Ephemeral build/cache was removed with containers.

Evidence: `private:simulator/dwt-auth-main-audit-bw579-02/{report,cleanup-summary}.json`; its cases reference the final six runs. The DWT boundary in [previous retention/authentication response](boot-retention-auth-results.md) was resolved; actual recovery command completion is next. Existing installation/version matrix's physical authorization status was unchanged.
