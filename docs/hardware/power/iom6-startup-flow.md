# IOM6 Power and Initial Configuration on the EM9305 Path

bw-0242 in progress. This records the initial power/configuration stage. The subsequent [startup retention contract](iom6-retention-copy-contract.md) progressed through state save and power-down; current stop is GPIO117 reset/ready. **Full initialization and the first peer transfer are not yet complete.**

## Evidence and changes

IOM6 in pinned Apollo510 header/SVD inherits IOM0 register layout, with base 0x40056000, IRQ12, request/status mask 0x80. Forty-two source-contract checks comparing header/SVD SHA and original ARM were preserved. Original caller passes module 6 and references log string `am_devices_em9305_init`. This is source evidence of an EM9305 initialization path, not physical chip revision or peer protocol verification.

Optional iom6Power was added to `BlackwallG2StartupFixture` and connected to the existing shared-power dictionary. Default null retains existing blocking. Host adapter explicitly selects 2/4/5/6/7 and continuously separates guards around IOM6. No new power, CQ, or IRQ engine was created.

The first exploratory run produced an MSPICFG tagged bit 21 warning from the existing Apollo4 engine, rejected by the common runner. It was neither used as success evidence nor ignored. Apollo510 SVD defines MSPICFG+0x280 reset 0x00200000, mask 0x7ff70007, and WTFCPOL bit 21.

`spiConfigStorage`, default false, was added to `BlackwallStrictIom`. When selected it stores/reads only this configuration while retaining existing constraints and returns to source-reset value on reset/power-off. Instead of forwarding original 0 writes to the underlying tagged register and hiding warnings, it explicitly handles the required latch behavior. SPI transfer, full duplex, and peer responses were not implemented. Existing I2C profile and default SPI path remain.

## Current original execution results

| Condition | Result |
| --- | --- |
| Stock 2.4 active | power 80/on; after initial 15 writes/14 reads, CQFLAGS 0x40056234 read blocked at PC 0x581e82 |
| Stock 2.3 / CFW active | After same power/configuration stages, same CQFLAGS read blocked at PC 0x57ab2a |
| Stock 2.4 IOM6-unselected control | Exactly matches existing PC 0x494d78 power-request stop, CPU, instruction count, observations, and boundary |
| Stock 2.4 stuck-off | Request 80/status 0. Unpowered FIFOTHR 0x40056104←0x1010 write blocked at PC 0x581fa2. Zero successful IOM6 reads/writes |

SPI configuration stored value is 0 in all three active inputs. With CQ disabled, the original attempts to save a value including external flags at handle+0x884. Current input is unknown (-1); known software flags 64 were not returned as actual external inputs. IOM6 commands 0, CQ pairs 0, no peer. IRQ12 NVIC pending/clear was confirmed in unit tests, not original IOM6 ISR or physical IRQ verification.

The simulated result that original code continues attempting configuration after a power fault is not interpreted as safe fallback. Raw stuck-off trial was preserved as semantic failure because its negative expectation retained the active boundary. After checking actual store opcode/address/value and fault state against source, only a separate saved re-audit was performed. Execution model and raw report were not adjusted to fit, and native was not rerun.

UART0 bytes and IRQ8 and existing event prefix were preserved for each input. The request difference—0x8e80 in stock 2.3 and 0xe80 in the others—also remains from existing inputs. Complete execution, scheduling, or physical timing equivalence across inputs is not claimed. IOM6/guard tail was added only to post-pause report; observer hooks were not changed during execution.

## Verification material

- After confirming two native reds for missing constructor option, 31 IOM6 unit checks passed, including power, shared masks, preservation of other controllers, IRQ12, unknown peer rejection, width, guard, and SPI latch/reset.
- Eighty-two regressions connecting only the newly reviewed component to the existing frozen module 2 fixture matched original reports. Existing fixtures/historical builders were not regenerated.
- Host board 31 subset, 12 invalid inputs, three CLI preflights, two host selections, and 12 common-contract tests passed.
- Three original active, one control, one fault, and 146 saved-audit checks passed without native reruns. Success evidence has no warnings except the allowed translation-cache clamp.
- Validator was extended to verify named guard operation `cq-external-flags-unknown` as the exact expectation in the common plan. It is not renamed or equated with general read/write.

Inputs, logs, source snapshots, and audits are in private simulator `iom6-source-contract-01`, `iom6-unit-02`, `iom6-legacy-regression-01`, `iom6-board-01`, `iom6-main-01`, `iom6-stuck-off-main-01`, `iom6-stuck-off-verification-01`, and `iom6-verification-01`. `iom6-main-discovery-01` and native red material remain as failure records.

## Remaining work

Limited CQFLAGS save/restore consumption was established in a subsequent contract. Within bw-0242, continue investigating EM9305 reset/ready, GPIO117 input, and first-transfer contract. Do not automatically inject mock 0 without source-justified virtual peer/input state. Do not mark work complete before reaching full IOM6 initialization and first transfer or a verified unsupported-peer boundary.

Missing-font diagnostic profile, synthetic initial values, and immediate power response are existing scenario conditions. Normal font-bank, main app loop, integrated display, and real-device installation/recovery remain incomplete. No device scanning, connection, RAM payload, flash, OTA, or permanent write occurred. Product progress remains 13/29=44.8%.
