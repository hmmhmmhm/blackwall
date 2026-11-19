# GAF on-demand requests and error propagation contract

bw-0354. The latest natural M55 main boundary remains the first request `7c000402` after [explicit trim and 225-byte storage](imu-clock-variation-contract.md). This work executed the original ARM service helper in isolated Unicorn M7. It did not execute internal EDMP service code or move the natural main stop.

## Confirmed transactions

Original helpers in stock 2.4/2.3/Faceclaw each perform the following. Initial register values are explicit synthetic inputs and do not mean all bits are valid on the actual device.

| Order | Original action | Preservation rule confirmed |
| --- | --- | --- |
| 1 | Write service ID 2 or 4 as one byte to SRAM0004 | Pass argument byte |
| 2 | Read/write A272 | Clear bit 5, preserve other bits |
| 3 | Read/write 2A | Set bit 6, preserve other bits |
| 4 | Read/write 73 | Set bit 5, preserve other bits |
| 5 | Call sleep 200 µs | This test has no callback, so not evidence of elapsed time |
| 6 | Wait for idle bit at A297 | If busy, call sleep 5 µs then reread; return on ready or error/timeout |

TDK [dynamic_service_request](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp.c#L197) and [GAF setter](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_edmp.c#L594) describe request 2 as complex parameter calculation and request 4 as bias calculation. Afterwards on-demand is masked, EDMP disabled, and idle awaited again. The three waits and request sequence in the existing original full setter also match this code.

## Important failure-path behavior

The helper continues subsequent transactions while accumulating I/O errors. Even if it waits for busy→ready completion, it does not clear earlier errors and return success. If an idle read returns both error and a busy byte, it calls sleep 5 µs once before exiting on the loop's status condition. The first inspector failed because it did not expect this last wait; it was corrected to match original behavior. Original code was not changed.

Pinned timeout evidence from the existing original full setter was also reused after hash verification. All three images return timeout (-4) after 200,000 polls at each wait. **Even after the first timeout, request 4, mask/disable, and calmag patch writes are still attempted.** Observing subsequent writes or function progress must not be judged service success. Final error return and each service result must be checked together.

## Verification scope

- 132 original helper scenarios: per image, request 2/4 × six initial bytes × busy 0/1/3 times = 36, plus four I/O errors for each request = eight, total 44.
- Original main was reidentified from the pinned bundle and the helper confirmed as both actual setter call targets. Original instructions were not reimplemented.
- Only I/O leaves were replaced with synthetic register/read/write ABIs. Error tests also supply read data and record write attempts. They do not claim valid data or device writes during actual bus errors.
- Actual helper register preservation, transaction order, sleep call arguments, poll counts, error returns, SP restoration, and unchanged guest SRAM were checked. No sleep callback, physical time, RF, or sensor computation was verified.
- Rerun with frozen inspector and dependencies yielded byte-identical final JSON. The previous full-setter timeout test was not rerun; pinned result hash and judgments were checked.

Final evidence is private `~/Library/Application Support/Blackwall/simulator/imu-gaf-service-contract-01/{report.json,frozen-report-02.json,manifest.json}`. First inspector failure is described in `imu-gaf-service-first-attempt.json`. Tool: `tools/inspect_imu_gaf_service.py`; output requires a new path.

## Boundary for next implementation

The driver's expected request, RMW, wait, and error contract is confirmed. The computed results requests 2/4 produce in EDMP internal SRAM and algorithm execution remain unverified. A model that merely returns ready and leaves RAM unchanged could pass this helper test but **is not evidence of implemented normal GAF computation**.

A follow-up model must distinguish support for request recording, trigger, pending, completion/error, and computational effects. Access requiring unsupported results must be strictly rejected. Paths testing service/device failures as virtual inputs must also be distinguished from normal completion. Current guards were not relaxed and automatic ready was not added. Registration of a new CFW candidate and same-scenario comparison (E04/E15) remain independent incomplete product requirements; this sensor contract investigation does not replace them.

Current natural main and model remain at bw353, with zero new native runs. E05/E12, overall 3/16, API checklist 3/6, and bw351 deferred status remain. No physical access, installation, persistent writes, or external publication occurred.
