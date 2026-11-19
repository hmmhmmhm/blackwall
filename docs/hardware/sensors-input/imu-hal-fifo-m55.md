# Original M55 HAL FIFO read and sample consumption

bw469 connected **original ARM HAL → actual Renode IOM4 → FIFO adapter → original parser/registered callback → sample ring** in an isolated M55 call test on stock 2.4. This is not successful sensor processing during natural main reset. E12 remains partial; overall 10/16=62.5%.

## Test contract

`tools/run_imu_hal_fifo_m55.py` reads pinned stock main and full SRAM snapshot. It identifies actual IOM4 handle 0x20040b28 from original I²C helper literals/table. Using collected descriptor format, it calls register 0x12 select/read two bytes twice and 0x14 select/read 32 bytes once. ARM HAL 0x5820d8 executes unchanged, with no transport, poll, or return stubs.

The caller is separately compiled synthetic ARM code. Initial IOM power/clock/configuration and two virtual raw16 packets are test inputs. They are not substitute evidence for natural RTOS calls or sensor initialization. Main code/branches/returns, TCB, gate, and GAF ready are unchanged.

`--parse` finally calls original array parser 0x552fa6. It checks the device's existing callback 0x4c4c6d and uncompressed state, while frame size 16/endian 0 and initial ring header/sentinel are explicitly prepared. This configuration is not claimed to arise naturally from stock initialization.

## Results

- HAL only: all six original calls returned 0. Both counts were 2 and 32 data bytes matched. Six actual IOM commands, three FIFO transactions, ten chunks, and two packets consumed.
- With parser: all seven original calls returned 0. Actual callback stored two samples in the ring and updated index to 2.
- An independent saved audit compared all 2252 ring bytes against calculated expectations, including raw axes, accel/gyro float conversion, timestamp per mode table, flags, and unused slots.
- Full SRAM of parser execution was exact against HAL-only control except explicit ring/device inputs. Final main ROM hash unchanged, CFSR/HFSR 0, execution guard violations 0.
- Audit passed 29 judgments. Owned containers from six runs were confirmed journal removed and absent in Docker inspect. Four earlier failures were also preserved.

Only stock 2.4 was newly run. The same connection remains unverified for stock 2.3/Faceclaw. Samples are synthetic raw packets, not verification of physical sensor samples, timing, or power. With memoryGuard=false allowing MMIO and callback SRAM writes, final ROM/SRAM comparison is not evidence of monitoring all transient writes. Execution address-boundary guard remained.

## Failures and reproduction

The first two runs ended before ARM start due to an incorrect power-object path. The next two rejected IOM preparation writes because status read was missing after power request. Comparison with existing units and power state machine led to `TryWrite` → `ReadStatus` preparation. Merely changing a direct method to a bus write did not solve it; model/guest were not modified.

```sh
<private-python> tools/run_imu_hal_fifo_m55.py <simulator> <new-output>
<private-python> tools/run_imu_hal_fifo_m55.py <simulator> <new-output> --parse
```

Evidence outside Git: `simulator/imu-hal-fifo-m55-01` through `05`, `imu-hal-fifo-m55-parser-01`, `imu-hal-fifo-m55-research-01/audit.py`, `audit.json`, frozen source, and `imu-hal-fifo-m55-manifest.json`.

The next boundary is the original upper FIFO read function calling HAL on a board including RTOS/sensor state. GPIO38 watermark/status, guest flush lifetime, and normal GAF initialization remain. Do not force the gate open and report a natural path. No physical access, external publication, or subagent execution.
