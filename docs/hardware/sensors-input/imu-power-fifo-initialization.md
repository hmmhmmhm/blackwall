# IMU power-off and FIFO initialization

bw-0328. The path after [EDMP quiesce and idle wait](imu-edmp-quiesce-lifecycle.md) was connected. Original M55 main in stock 2.4, 2.3, and Faceclaw executed accelerometer/gyroscope mode 0, FIFO flush, and two status queries, reaching IOC pad register 30 lookup. Only original ODR function fields and RMW were verified; configuration in natural main remains incomplete.

## Actual sequence and original contract

The original caller sets accel bits 0..1 and gyro bits 2..3 of `PWR_MGMT0(10)` to mode 0 separately. Each setter first checks indirect SREG endianness, then RMWs only its power-byte field. Other fields and the upper four bits are preserved. Low-four-bit ODR setters of `ACCEL_CONFIG0(1b)` and `GYRO_CONFIG0(1c)` were also confirmed in independent ARM fragments, but this native path had not yet called them.

Next it reads `FIFO_CONFIG2(20)`, sets bit 7, and calls a 10 µs callback. Original code rereads the register to check bit 7 cleared; if busy it repeats a 100 µs callback and counter decrement. Initial counter is 1,000,000. This counter is not interpreted as actual total wall-clock timeout; the full timeout loop was not execution-verified.

After the error-0 gate, it reads two bytes each from `19/1a` and `3b/3c`, expands them into 15 and 14 boolean fields, and stores them in two caller buffers. Bit 3 of `3c` is skipped. Actual bit order was compared in native SRAM even with nonzero status.

`inspect_imu_power.py` verifies source audits, main, SRAM, and existing flow hashes for three images. It links current power read-return to the actual caller and checks mode-0 arguments. It checks 7,332 independent ARM fragments covering field RMW, status-OR return, flush request/busy decision, and status-bit expansion. The initial inspector failed by mistaking the caller's last instruction for BL; it was corrected to select the actual BL, preserving failed code and logs.

## Model scope

Optional `powerConfigurationHex` explicitly specifies six bytes in order: power10, FIFO20, status19, 1a, 3b, 3c. These are not inferred actual reset values or physical pending events. Initial FIFO flush bit 7 must be 0.

`BlackwallImuPowerConfiguration` permits changes to only one power field after a read lease. Upper-four-bit changes or simultaneous changes to both mode fields are rejected. FIFO permits only setting bit 7 of the byte read; a timer clears bit 7 after declared virtual time. A negative profile that never completes is also provided. Reset initializes timer, leases, and counters.

The two status pairs are explicit snapshots readable only after FIFO completion. This is not a model of actual IRQ generation, event injection, or repeated read-clear latch behavior. ODR registers 1b/1c are not yet supported by the peer and are not arbitrarily returned as 0. There is no actual sensor sample or FIFO data engine.

It is used as an option of shared `prepare_imu_ireg_candidate.py`; no native runner was added. Five prior IREG, FSYNC, INT1, EDMP, and idle-nonresponse plan paths matched previous plans except current model SHA. Existing captures are reused via private case symlinks without moving or overwriting.

## Natural M55 results

| Input | Initial power/FIFO | Final power/FIFO | Power RMW | FIFO queries | Next request |
| --- | --- | --- | ---: | ---: | --- |
| Stock 2.4 | `af/25` | `a0/25` | 2 | 3 | address 69/register 30 |
| Stock 2.3 | `af/25` | `a0/25` | 2 | 3 | Same request |
| Faceclaw | `af/25` | `a0/25` | 2 | 3 | Same request |
| Stock 2.4 control | `5b/5a` | `50/5a` | 2 | 3 | Same request |

Each normal run performed one FIFO flush request/completion and one read of each status pair. 66 completed I²C finishes, 26 received bytes, and five indirect lookups were confirmed. Next HAL descriptor address, direction, length, and TX byte also matched actual SRAM. Control status bytes `a5/5a`, `12/34` appeared in the original caller's output buffers in exact boolean order. These are virtual inputs, not claimed physically valid event combinations.

The disabled control exactly matched CPU state and all observed events from the previous EDMP-only run. Previous event prefixes of four normal runs were also preserved. The never-completing FIFO profile confirmed three busy rereads, zero completions, zero subsequent status reads, and zero event loss. The host checks query count at 10 ms intervals only to end collection; it does not change guest branches, returns, or timeout. This does not verify all behavior after the short observation.

The initial stock24 provisional boundary contract failure was audited under a separate semantic plan while preserving original report/plan. Firmware instructions, branches, and returns were not modified and no CPU hook was added.

## Verification assets and remaining work

All report values matched between 133 unit and 133 frozen checks; 7,332 original and 7,332 frozen fragments passed. Source report/inspector artifacts were byte-identical. 473 Python sources matched frozen source and passed syntax checks; this is not functional testing of every tool. Nine existing peripheral models were unchanged and one IMU peer extended.

Six valid native runs, six separate saved audits, and four normal-consumption-state checks are preserved in private `simulator/imu-power-verification-01/manifest.json`.

Next register 30 is `IOC_PAD_SCENARIO_AUX_OVRD` in the pinned TDK header. Stock24 static analysis found the original helper sets bit 4 and changes bits 2..3 to 1. Subsequent auxiliary interface initialization precedes ODR. Compatibility of this subsequent behavior across three versions, separate sensor identification, and actual transfers are next investigations, not counted as successes.

Actual ODR execution, full sensor initialization, sample/interrupt, and full boot/UI remain incomplete. Continue toward nonzero main draw and framebuffer/576×288 viewer. Overall scope v2 remains 13/29=44.8%; no physical connection, installation, or persistent writes.
