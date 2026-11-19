# EDMP service busy/completion and original main integration

bw-0333 connected the [original initialization contract](imu-edmp-initialization-contract.md) to the Renode IMU model. **Original main in stock 2.4, 2.3, and pinned Faceclaw CFW completed SRAM initialization and decimation requests and advanced to the next IMU SRAM `0048` read.** CPU instructions, branches, returns, and firmware bytes were unchanged. No physical device was used.

## Supported behavior

`BlackwallImuEdmpService` is enabled only by explicit option. It validates IRQ program addresses `4000/4004/4008`, stack high byte `02`, SRAM power, and exact service request parameters. It reuses existing indirect-transfer address/data continuation and the 4 µs access model.

Service requests follow `0118=01000000`, `011c=0000`, `0120=0018`, `011e=00`. The model becomes busy only with valid enable, interrupt mask, and host message prepared. At first completion after virtual time, it clears 6,144 bytes of IMU model RAM `0000..17ff`. The second request records decimation service completion distinctly. Prior disable/idle completion is not reused as completion of a new request.

This is not an instruction emulator for the IMU's internal dedicated processor. The decimation service provides limited host-visible completion status and does not calculate filters, sensor fusion, or all ROM defaults. The next `0048` read is unsupported and stops at a strict boundary. Required ROM initialization results are not filled with arbitrary success values.

Default inputs are register fixture `a5b6c7d8e9` (`a2a7,a271,a272,a273,73`), RAM fill `a5`, and completion delay 1,000 µs. All are explicit simulator inputs, not measurements of physical reset values or processing time. Disallowed programs, parameters, addresses, and writes during busy are rejected before model application. Support is limited to the two services required by the current original calls.

## Verification results

- Three original mains recorded seven program-byte writes, nine SRAM parameter writes, two service starts/completions each, one decimation completion, and 6,144-byte RAM clear. Enable 0/1 were restored to `f2/8f`. Six previous accelerometer settings and 13 magnetometer completions were retained.
- Descriptor locations were derived from actual HAL prologue/callers in all three captures. Address `69`, length 3, write direction, and payload `7c0048` were confirmed in SRAM. This establishes the next request as an IMU SRAM address selection; data reception at that address was not performed.
- The service-disabled control exactly matched bw331 CPU state and all selected events. Three normal images plus disabled and missing completion make five native runs and five saved reaudits. No selected events were lost.
- Missing completion was observed through four idle queries with one start, zero completions, zero bytes cleared, and pending retained, then stopped by the host. This is not execution through a full one-second virtual timeout or watchdog.
- 333 unit checks and 333 frozen-source checks passed. They covered RAM preservation while busy, delay boundaries, full clear range and preservation of 2 KB outside it, invalid-parameter rejection, missing completion, and reset cancellation in progress. Counts are cumulative and include existing model checks.
- Ten existing peripherals/observers retained their hashes; only one IMU model changed. 481 Python sources were frozen and syntax-checked. Syntax checks are not counted as functional tests. The previous ODR planner matched except for the current IMU SHA.

Import failure with the previous model lacking the new class was confirmed before implementation. The initial native 2.4 capture and existing prefix were valid, but the provisional `bounded-capture` semantic contract failed because it differed from the actual strict boundary. The capture was not changed; it was separately reaudited against the final strict semantic contract. The failure record was preserved.

The pinned manifest was reused for bw332's 36 original ARM wrapper and 12 caller-gate conditions. That standalone analysis substitutes bus/SRAM/delay callees and is distinct from this natural M55 execution.

## Evidence and next work

Code is in `tools/renode-imu-identity.cs`, `tools/verify_imu_edmp_service.py`, and shared planner `tools/prepare_imu_ireg_candidate.py`. Proprietary images, SRAM, and native logs remain outside Git under `~/Library/Application Support/Blackwall/simulator/`.

- `imu-edmp-service-main-01/{stock24,stock23,cfw}`: normal runs.
- `imu-edmp-service-control-01`, `imu-edmp-service-missing-01`: controls.
- `imu-edmp-service-saved-audit-01`: separate saved audit.
- `imu-edmp-service-verification-01/manifest.json`: pinned input, code, and verification hashes.

Next identify the original consumer of SRAM `0048` and the data contract ROM initialization must provide. Distinguish inferred fixtures from confirmed initialization results, then continue to external ODR/FIFO configuration and nonzero main frame/viewer. Overall scope v2 remains **13/29 = 44.8%**. Full boot, application loop, integrated screen, physical sensor, and physical-device recovery remain incomplete.
