# FIFO threshold and GPIO38 integration plan

bw475. This follows [original FIFO configuration](imu-fifo-native-configuration.md) in the approved E12 sensor-input integration sequence. Apply the brainstorming design review within the existing approval scope. Do not add authorization for physical devices, external publication, or CFW, or a separate approval requirement.

Choice: route the existing threshold IRQ through a small IGPIOReceiver connector to pin 38 of the existing GPIO owner. Accept a rising edge when actual PINCFG38=0x93; the existing GPIO handles bank 1 mask, pending, W1C, and NVIC57. A separate GPIO controller would duplicate ownership, and direct IRQ injection into the CPU would bypass pad/status/clear, so neither is selected.

The connector is opt-in and rejects platform load without a runtimePin38/config owner. A high with an incompatible actual pad creates no new GPIO edge and is counted as rejected. Low lowers the existing level. Do not assume pad reconfiguration automatically recreates an IRQ while active-high; the next low→high transition is required. GPIO W1C is independent of threshold status. Original register 18 low 3 bits=1 specify push-pull, active-high, pulse, so the final connection lowers the physical line with the specified 8 µs timer. FIFO status read acknowledges the logical threshold input and does not lower the line before the pulse minimum-on time. Latch is a separate unit profile. This connection test does not guarantee recovery from every reset.

Verification:
1. Preserve the platform-load red test for the new connector, then implement the minimum.
2. Unit-test actual IOM FIFO enqueue→threshold→pin38→bank1/NVIC57, separate W1C and status-read lifetimes, invalid pad, mask, held-high, reassertion, and reset. Retain existing threshold/configuration tests.
3. Verify pinned stock24 original main getter hold→explicit native setter→WM10 occurrence→original ISR/registered callback→return to the existing interrupted Thread. Gate 0 and unconsumed samples are the correct result for the current initialization state. A subsequent explicit API consumer diagnosis can check data and line-release boundaries. Do not call this path successful natural initialization.
4. Audit equivalent observer on/off results and CPU/SRAM/WORK, original code/config owner, execution boundaries, and owned container cleanup against saved inputs. Patching original main/TCB/gate/ready is prohibited.

Normal GAF/EDMP computation and natural sensor-task consumption remain separately incomplete. This diagnosis does not raise E12 completion.

During execution the initial latch assumption was corrected against original INT1 configuration and DS-000595 §16.23/21.53. The initial native01 pair is isolated as a latch case; use the final pulse02 pair. Results and limits are in the [integration record](imu-fifo-gpio-irq-integration.md).
