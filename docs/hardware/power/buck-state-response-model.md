# Virtual Buck Response Checking Request Order

Work `bw-0026` is partial S3/S6 progress. No physical access, RAM payload, OTA, or permanent write occurred. Full app loop and integrated display remain incomplete, and the installation gate is unchanged.

## Confirmed original path

The second `0x40021108` read after [D-cache initialization](../cpu-memory/coherent-data-cache-model.md) is a condition check before selecting high-performance MCU mode. Read PC is `0x4888c4` for stock 2.3/Faceclaw and `0x4947ac` for stock 2.4. Original code extracts SIMOBUCKST bits 4–5 and checks for ACT=3. Pinned public HAL `am_hal_pwrctrl_mcu_mode_select()` also returns INVALID_OPERATION if not ACT for an HP request. It is not interpreted as a simple readiness wait loop.

Supplying ACT on the first status read executes the earlier `vddc_vddf_tempco()` branch. Public `am_hal_spotmgr_pcm2_0.c` and original instructions confirm reducing VDDF trim by 10 with saturation at 0 in the initial low/mid range without GPU boost. Public reset fixture field 64 becomes 54, and full word `0x1fefc0` becomes `0x1fefb6`. Pinned source hashes and evidence are private `buck-response-verification-01/source-audit.json`.

## Optional digital response

`--buck-response-model active|stuck-off` is separate from the existing single status sample. Selecting both is rejected before execution. Default selects neither.

1. Initial virtual state is off.
2. Completing the existing three ordered buck enable requests changes it to requested.
3. On the first DWORD status read after two post-enable memory-LDO configuration stages complete, it becomes active or stuck-off according to the explicit profile.
4. Subsequent reads retain that state; read count does not cause a transition.

Completion assumes **immediate application on the first eligible read**. Voltage, analog stabilization, failure probability, actual time, and manufacturing calibration are not reproduced. Other VRSTATUS fields are assumed 0, not measured G2 values. Partial accesses and subsequent reads before readiness are blocked. stuck-off is a virtual fault input, not a physical failure distribution.

`--vddf-tempco-storage` can be selected only with the new response model. After confirming ACT response, memory-LDO completion, at least two reads of that word, and retention of its initial value, it stores one initial VDDF field reduction in the virtual register. Other bits, values, addresses, widths, and repeated writes are blocked. It does not model periodic temperature correction, GPU/SDIO boost, voltage effects, or valid calibration.

## Actual main and regression results

Six combinations of stock 2.3/2.4/Faceclaw38 × initial main LP/HP were compared. Both engines matched next PC, MMIO address/width/requested value, cache state/counters, buck response transitions/read count, and VDDF storage. Original main was unchanged.

After ACT check and virtual trim storage, cache initialization runs and stops at an attempted word `0xfbbfe0` write to `CLKGEN.MISC` address `0x40004044`. Stock 2.4 PC is `0x494698`; per-image PC/hash are in the comparison report. The clock write was not applied. There were no memory protection/system-control violations or unexpected native engine messages.

- 116 Python tests passed, including 34 subconditions in one cache fixture.
- Native 18 conditions comprise 13 response/correction and five existing blocking regressions. They cover nominal/stuck-off, pre-ready reads, byte/halfword, prohibited writes, invalid correction/order/repetition, and unselected blocking.
- Stock 2.4 LP with response off stops at the existing second VRSTATUS read.
- Stock 2.4 LP Python stuck-off execution stops on `0xe000ed24` read without applying trim. Agreement of that handler with actual fault recovery and the native fault path remains unverified.

The first native execution did not apply the response because late option-binding code did not account for the guard base moving to `0x40001000` on a board with reset controller. Failure material was preserved; target-match count and actual profile-binding verification were added. Corrected native and Python results matched. An earlier native stock 2.4 LP result was reused in the six-combination comparison after checking frozen source, conditions, and hashes.

## Reproduction and next work

```sh
python3 tools/firmware_runner.py /private/stock-2.4.0.24.bin \
  --scenario startup-zero-info1-rev-23-buck-response-active-hypothesis \
  --output /private/new-buck-response.json
python3 tools/compare_dcache_startup.py /private/verified-bundles \
  /private/new-buck-comparison --buck-response active
```

The current Mac uses Python in private `simulator/venv-02`. Evidence under `~/Library/Application Support/Blackwall/simulator/` outside Git:

- `buck-response-verification-01/`: source audit, Python regression, OFF/stuck-off observations.
- `buck-response-native-final-01/report.json`: 18 native conditions.
- `buck-response-main-comparison-01/report.json`: six actual-main combinations and source/result hashes.
- `buck-response-main-stock24-lp-01` and `02`: option not applied and corrected earlier native runs.

Next are clock request/response for high-performance mode transition and public HAL wait/error paths. Do not unconditionally allow current clock storage or return constant success ACK. Confirm request order and supported scope to continue connecting full main startup and display.
