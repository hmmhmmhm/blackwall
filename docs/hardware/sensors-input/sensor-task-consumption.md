# Natural FIFO sample consumption by the original sensor task

bw-0489. **E12 was completed.** In original main of stock 2.4, stock 2.3, and Faceclaw38, device FIFO samples → GPIO38/IRQ57 → original `sensor_hub` consumption → numerical and stored results were verified. Product acceptance is **16/16=100%**; overall Goal completion is decided after a separate final audit.

Earlier [bw475](imu-fifo-gpio-irq-integration.md) used gate-0 IRQ and separate synthetic API consumption. This run uses gate-1/FIFO-ready state after normal main completed original initialization. No CPU caller, function return, TCB, gate, frame-size, or ready was injected.

## Device and original path

The pinned E06 board and main reset → UI/screen path were reused. Original setter had already configured FIFO32/WM10. Existing `runtimePin38`/NVIC57 wiring and verified `BlackwallImuInt1Gpio` were added. No new device algorithm was made and existing FIFO, configuration, and transport models were unchanged.

`10×32-byte device FIFO input → watermark → INT1 pulse → GPIO38/IRQ57 → original ISR/callback → original queue message → sensor_hub/Thread → original status/count/data/parser → sample callback/auxiliary decoder → axis conversion → result ring`

Original INT1 config is 0xa1 low 3 bits=1, PINCFG38 is 0x93. The 8 µs pulse is an existing declared model, not physical timing measurement. General registers, instruction count, full SRAM, and virtual time were exact before/after enqueue. NVIC pending/FIFO/IRQ device-state changes are intended external input.

## Actual results across three originals

| Item | Stock 2.4 | Stock 2.3 | Faceclaw38 |
| --- | --- | --- | --- |
| Initial gate/FIFO | 1/ready/32 bytes/WM10 | Same | Same |
| Actual IRQ callback | IPSR73, once | Same | Same |
| Consumer Thread | `sensor_hub` | Same | Same |
| FIFO consumption | 10 packets, 0 remaining | Same | Same |
| Additional FIFO transactions | 4 | Same | Same |
| Raw FIFO read bytes | 324 | Same | Same |
| Sample header | 5931/10/10 | 5817/10/10 | 5799/10/10 |
| Screen counter over next 100 ms | 7→12 | 7→12 | 7→12 |
| Fault/guard/memory-policy violations | 0 | 0 | 0 |

324 bytes are two count reads × two bytes plus 320 data bytes. Status read uses a separate transport path. Four transactions are status/count/count/data, not all I²C hardware commands. One threshold acknowledgement occurred; GPIO pending/IRQ, pulse line, and threshold pending all cleared.

The header's first word matches the original consumer function's actual timestamp argument, not a synthetic sentinel. Each no-input control had no IRQ/sample consumption over 100 ms and preserved the 2252-byte ring. The screen also updated in controls. General CPU/time at start differs slightly according to initial screen observation boundary, so full CPU/SRAM exactness between pairs is not claimed. Same main/model/board/run, initial sensor configuration, and empty ring were confirmed.

For the two older families, original sample callback and auxiliary decoder were each observed ten times, batch processing once, matrix application 20 times, and actual return to upper consumer caller. For stock 2.4, existing trace was reused to verify original consumption/parser, subsequent transformed results, and 100 ms progress; direct observation of full upper-function return is not separately claimed.

## Numerical verification and root cause

Reusing the old API fixture's expected values produced 206 differing bytes. Raw axes, timestamp, and flags matched, but floats differed. Source tracing showed the old fixture stopped immediately after parser return, while the actual natural path subsequently performs original 3×3 axis transformation. No firmware or FPU model error was assumed or changed.

Independent formulas read original-initialized mode/period/bias and actual matrix from before SRAM. They reflect signed32→float32, scale/bias, and float32 multiply/accumulate order. Time, six raw axes, transformed floats, flags, and unused slots for every sample matched **all 2252 bytes exactly in all three originals**. Matrices were preserved before/after.

Original auxiliary-data decoder ARM also ran separately on M7 with the same initial SRAM and FIFO ES payload. It returned normally without ABI stubs, preserved full SRAM, and its 80-byte result matched actual natural M55 output. This is not described as physical magnetometer/sensor-fusion correctness or actual EDMP ROM execution. Individual decoder and transport, consumption, and transformation were verified.

Current assumptions for cold sensor service, virtual auxiliary data, and reference GPU model remain. Numerical GAF/EDMP fusion, physical sample timing/unit accuracy, power, and optical output were not certified.

## Execution, audit, and preserved failures

```sh
<private-python> tools/run_imu_task_input.py <new-private-input> --case stock24
<private-python> tools/run_imu_task_input.py <new-private-control> --case stock24 --control
# Run stock23/cfw sequentially in new outputs as well.
python3 tools/audit_sensor_acceptance.py <private-simulator-root> <new-private-audit>
```

`run_imu_task_input.py` separates schema2 execution and semantic judgment. `audit_sensor_acceptance.py` checks saved three input/control pairs, original ABI/numerics, pinned boot prefix, and only permitted device connection changes. Audit creates neither a model nor new native runs. Only stdlib source was frozen and reaudited in `/tmp` with empty PYTHONPATH; report was byte exact.

Nine semantic negatives changing observed/SRAM values—raw axes, float, time, unused tail, IRQ context, consumer task, consumption count, remaining IRQ, and control consumption—were all rejected. Actual original captures were unchanged. A partial case failure/omission cannot pass full E12.

There were seven new native runs. The first ended on a device-name lookup error before sample injection and was preserved. Six using actual existing fixture `transport.RawFifo`/`Threshold` access (three inputs/three controls) succeeded. Pinned reference/calculation procedure and initially incorrect math expectations were preserved. Isolated codec runs were initial one + three originals + three frozen reproductions = seven and are not added to native counts. Fourteen Python dependencies of the independent oracle were frozen.

Actual absence of all seven owned containers was confirmed. No physical access, flash/OTA/MRAM writes, subagents, or GitHub publication.

Private materials: `simulator/imu-natural-task-*`, `sensor-acceptance-01..02`, `sensor-acceptance-frozen-01..02`, `sensor-semantic-negatives-01`, `sensor-acceptance-manifest.json`. Next is the final audit comparing requirements for all 16 conditions, original evidence, commands, development tools, and remaining limits.
