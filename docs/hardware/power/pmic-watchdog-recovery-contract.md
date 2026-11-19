# Software Contract for the PMIC Watchdog and Recovery Patch

bw-0140. Original timer arguments were compared with recovery patch expectations. No PMIC timer command had yet been accepted; no physical device, Astra, or external publication was used.

## Original intent and actual call arguments

The original timer configuration function uses a 12-byte structure copied by its caller. After confirming per-image unique prefixes, original BL, literals, and LDM/STM copies, a read-only RAM snapshot preserved the structure at the first function-entry hit.

| Input | Function entry | Flash and live RAM values |
| --- | --- | --- |
| Stock 2.4 | 0x580680 | mode 2, prescaler 1, target 0x003c00 |
| Stock 2.3 | 0x57d648 | Same |
| Faceclaw38 | 0x57d648 | Same |

Hook R0 also matched the timer object at original PMIC instance+0x84. PC, returns, and RAM were not written; the existing strict endpoint and MMIO counters remained. Execution currently stops at the timer configuration write itself.

The [Nordic timer specification](https://docs.nordicsemi.com/r/bundle/ps_npm1300/page/chapters/core_components/timer/doc/frontpage.html) describes a 24-bit timer and configuration → target bytes → strobe → start procedure. Mode 2 is watchdog reset and prescaler 1 is a nominal 2 ms tick. Thus 0x3c00 × 2 ms = **30720 ms (30.72 seconds)** is a calculation of configuration intent, not a measured clock, timer start, or expiry time.

The original task table is `[0x0700,0x0701,0x0703,0x0704]`, consistent with start/stop/strobe/kick respectively. Original 2.4 also has separate start and kick helpers; these were not reached in this dynamic execution. Instructions sending three target bytes high/mid/low and strobing were also confirmed in the configuration setter. Static evidence is preserved in `pmic-watchdog-source-contract-01/report.json`.

## PMIC feed already in the recovery patch

[watchdog.h](https://github.com/drdaeman/g2-bootloader-patch/blob/6198d70e18293caebf8314d2e40bd3b1d0a5ee16/src/watchdog.h) and bootloader.c from upstream g2-bootloader-patch commit `6198d70e18293caebf8314d2e40bd3b1d0a5ee16` were fetched again and verified by Git blob/SHA256. Both files are byte-identical to existing local 2.3 and 2.4 candidates. It would therefore be incorrect to say there is no external PMIC feed code.

The feed reads configuration and target on IOM7/address 0x6b and kicks only the known 0x0a and 0x003c00 profile. Original flash/live arguments here **match at the software level**. TIMERSTATUS and reserved byte are excluded from verification; the profile itself is not rewritten.

- Pointer 0705: IOM command 0x281, using CONT.
- Six-byte read: command 0x602.
- WATCHDOGKICK 0704=1: command 0x301.

Before feeding, it checks IOM power ownership and GPIO22/23 configuration and does not touch the bus if busy or changed. It is implemented to temporarily enable power then restore original power, debug enable, and PRIMASK state. Individual attempts have DWT-cycle and polling-count limits. This does not guarantee termination of the whole manager or successful retries.

The held manager attempts feed when not receiving, using 5120-tick success and 1024-tick failure intervals. Actual RTOS tick period, priority, RAM payload interrupt masking, and coexistence with prolonged reception need separate verification. A source comment about a right-temple RAM test is distinguished as a developer test claim, not our physical-device verification.

Existing upstream test_watchdog.py also executes compiled feed against mocked MMIO. Some manager tests stub feed. Existing tests are neither reduced to Apollo internal-watchdog-only tests nor expanded into physical PMIC timer/recovery verification. The existing suite was not rerun here.

## Difference from current simulator

bw-0141 added an optional [virtual watchdog model](pmic-virtual-watchdog.md). Existing default PMIC retains the STOP subset. The optional model supports fragmented target frames and pointer → read needed for CONT only on timer registers. Read-six status/reserved bytes are rejected without explicit mocks. Virtual 500 Hz warning/kick/expiry and reset request/stop were tested, but physical reset was not implemented. bw-0142's [pinned feed ARM integration](../../bootloader/recovery-pmic-feed-integration.md) confirmed CONT/read6(4+2)/kick and profile/power/pin rejection and PRIMASK preservation under explicit mocks. Power distinguishes guest off request from completion after host ReadStatus. DWT timeout, prolonged reception, and scheduler coexistence remain future work.

## Evidence and incomplete scope

`pmic-timer-profile-main-01/report.json` contains actual RAM/original profile results for three originals. The 64 checks in `pmic-watchdog-contract-verification-01/report.json` compared raw logs/observer, pinned main/image, all inputs unchanged except run.py read-only hooks, the same strict boundary, live arguments, original object, and upstream/local source. Source-string checks confirm the reviewed contract's presence, not runtime behavior.

Independent GPT-6-family review's points about nominal time, CONT compatibility, manager liveness, and scope of existing tests were incorporated. The parent separately audited final three original results. No transcript archive comparison occurred. Product conditions remain 13/29. Actual PMIC timer, per-device recovery, full boot, and display remain incomplete.
