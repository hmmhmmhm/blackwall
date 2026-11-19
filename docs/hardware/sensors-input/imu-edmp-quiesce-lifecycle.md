# IMU EDMP quiesce and idle lifecycle

bw-0327. Five original functions were connected after [INT1 configuration](imu-interrupt-configuration.md). M55 main in stock 2.4, 2.3, and Faceclaw executed original branches and calls, completed the EDMP idle wait, and reached the `PWR_MGMT0(10)` query. Power configuration itself and full boot are not yet verified.

## Original code sequence

| Order | register | Original RMW | Additional action |
| --- | --- | --- | --- |
| 1 | `2a` | `& ef` | Clear GAF bit 4 |
| 2 | `29` | `& fb` | If resulting bit 3 is 0, `2a & df` |
| 3 | `29` | `& f7` | If resulting bit 2 is 0, `2a & df` |
| 4 | `29` | `& fe` | Clear bit 0 |
| 5 | `2a` | `& bf` | Clear core bit 6, then wait for idle |

In the pinned public TDK header, register 29 bits 2 and 3 are reserved. G2's original uses them for conditional deactivation. This difference is retained as legacy bits of unknown meaning, without concluding that the sensor differs or assigning specific feature names. Only the portions matching SDK GAF/core deactivation use those names.

The idle function checks bit 1 of indirect register `a297`. If busy, it requests 5 µs through the original callback and reduces the counter by 5. The initial counter is 1,000,000. Separate indirect-read waits and transfer time mean this is not interpreted as an actual one-second total timeout. The final counter boundary returns error `-4`; a read error also incurs one wait when busy.

`inspect_imu_edmp.py` checks 5,469 independent ARM fragments across the three images, covering 256 primary bytes, conditional branches, extra clears, idle decisions, and error/counter boundaries. It does not verify the complete timeout loop or physical wait time. The first test failed because it initialized idle error accumulation R4 differently from the original; failure code and logs were preserved before correction to R4=0.

## Limited peripheral model

The optional EDMP bank in `renode-imu-identity.cs` explicitly receives two initial bytes and a virtual idle delay. Initial values are not actual reset values. It allows observed single-bit clears and same-value writes only to registers first read by the original. Setting bits, multi-bit changes, and unsupported bit changes are rejected before state changes.

The core bit 6 transition 1→0 starts a virtual timer. A negative fixture that never raises the idle bit is also supplied. It does not substitute changes to CPU branches, returns, firmware instructions, or SRAM. Parent reset initializes timer and leases and is distinct from IOM controller reset. IRQ generation, actual EDMP algorithms, and sensor samples are not implemented.

EDMP options were added to shared `prepare_imu_ireg_candidate.py`. The existing IREG, FSYNC, and INT1 paths match previous plans except for the current model SHA. No new native runner was created.

## Natural M55 execution

| Input | Initial `29/2a` | Final `29/2a` | RMW writes | Idle reads | Next request |
| --- | --- | --- | ---: | ---: | --- |
| Stock 2.4 | `ff/ff` | `f2/8f` | 6 | 2 | Address 69, register 10 query |
| Stock 2.3 | `ff/ff` | `f2/8f` | 6 | 2 | Same request |
| Faceclaw | `ff/ff` | `f2/8f` | 6 | 2 | Same request |
| Stock 2.4 control | `00/7f` | `00/0f` | 7 | 2 | Same request |

The number of original conditional clears changes with different initial values. The model does not force final register values. Address, direction, length, and TX byte of the actual next HAL descriptor are checked in saved SRAM. Prior event prefixes were preserved in all normal runs.

The first run's provisional boundary contract is preserved as a failure. An attempt to change the saved capture's plan was also rejected by the SHA check; after restoring the original plan byte-for-byte, a separate semantic plan was used for audit. Execution inputs and prior failure reports were not overwritten to obtain an audit pass.

The negative test's short host observation limit was rejected before execution because the shared runner differs from the existing 120-second limit. The failed plan/log were preserved, and a new plan inherited the existing 120-second limit unchanged. Neither the shared runner nor guest timeout was modified.

The 120-second nonresponse run observed 1,806 original repeated queries, but the runner rejected it due to event buffer overflow. A subsequent run after changing host collection to end after at least two queries still advanced to 90 during a one-second host check interval, losing 56 events. Neither run counts as a pass. The follow-up plan checks the same condition at 10 ms host intervals while retaining the existing 120-second cap. This does not change guest timeout or return values, or turn busy into idle. The observation change is preserved as an explicit execution condition.

## Completed scope and next steps

Of eight native runs, six normal, control, and short nonresponse captures were verified by separate saved audits. Two long nonresponse captures remain preserved as rejected due to event loss. The disabled control exactly matched prior CPU state and all observed events. The short nonresponse capture confirmed two busy queries, zero idle completions, and zero event loss; it does not guarantee a full timeout run or safety at all later times.

All report values matched between 111 unit and 111 frozen cases. The 5,469 original ARM fragments and 5,469 frozen fragments passed, and report/inspector files were byte-identical. 471 Python sources matched frozen source and passed syntax checks. Nine existing peripheral models were unchanged, and one IMU peer was extended.

The verification bundle is preserved outside Git in `simulator/imu-edmp-verification-01/manifest.json`. Unit tests and frozen-source revalidation, original fragments, native captures, and saved audits are distinct evidence. Passing Python syntax checks does not mean all tools were functionally tested.

Next, connect the requested original power/ODR initialization in behavioral units, then proceed to nonzero draw in integrated main and the framebuffer/576×288 viewer. Physical IMU chip revision, physical timing, sample/interrupt, full boot/UI, and actual recovery remain unverified. No physical connection, installation, or persistent writes occurred. Overall completion remains scope v2 13/29=44.8%.
