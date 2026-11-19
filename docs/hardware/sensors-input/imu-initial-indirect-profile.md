# Explicit initial indirect readiness profile

bw-0358. The pre-reset IPREG_MISC boundary of the [identification failure path](imu-identity-failure-native.md) was extended with explicit virtual input. The default remains unknown. This does not verify physical glasses power-on state or normal boot.

## Input and state contract

`initialIregReady=true` is an **optional test assumption** that the initial indirect interface is ready. It requires an explicit SREG fixture and defaults to false. Initial access is allowed only when selected initial interface/drive values exist and reset request is 0. Once soft reset is requested, existing reset-completion and interface/drive restoration conditions still apply. This option cannot skip reset in progress or partial restoration. Host reset returns to the declared initial profile.

Existing address/length, 4 µs indirect access timer, and known response ranges remain. [Pinned TDK transport source](https://github.com/tdk-invn-oss/motion.arduino.ICM45608/blob/646f55a6ec119b59d9ebce47af660842b53e5506/src/imu/inv_imu_transport.c#L108) provides indirect address setup, wait, and byte-read procedures. That code does not guarantee actual G2 initial readiness. Git blobs/SHAs of two C/H files were verified and preserved in a private source manifest.

## Natural execution results

| Input | Original execution result |
| --- | --- |
| ID0 + initial ready, three originals | Device check R0=FFFFFFFF, reset 0 → existing response/timer path → bias/GAF 225-byte storage → strict stop at first service request `7c000402` |
| ID81 + initial ready, stock 2.4 | Original actually performs reset (request 1) → existing 225-byte/service boundary. Option does not skip normal reset |
| ID0 + default unknown, stock 2.4 | Previous `7ca297` boundary retained; exact against previous CPU/events |

The normal ID control was exact against bw357 normal control CPU report, events, and full SRAM. It is a fixed-input regression check, not a guarantee of completed boot or physical readiness. No GAF internal computation or successful response was added.

The three failure runs retain actual `sensor_hub` context and 29 linked tasks. Original main bytes are unchanged and strict source changes only the initial-state component. Actual guest stack binds root return LR, GAF setter push/locals and caller LR, on-demand helper LR/request 2, and current SP active stack range together. A single coincidental code address on stack was not treated as an active frame.

The initial driver returned FFFFFFFF, but **local R4 of a separate configuration caller was 0** at the GAF call. This is not the entire initialization result. It shows initial error and later configuration counter/local state must not be combined into one success judgment. Upper sensor initializer and wrapper returns were not reached, and final error handling remains unverified.

## Checks and preservation

- 5,051 checks passed including existing checks. A constructor without the new option failed, then passed after implementation. Checks include initial 4 µs/default unknown, rejection during reset/partial restore, normal restore, host reset, and explicit fixture requirement.
- Five actual runs: three ID failures, one normal, one option off. Five saved semantic audits passed. A run whose initial provisional bounded expectation differed from actual strict boundary was not overwritten.
- Thirteen existing runner semantic contracts and rejection of two preparation-tool error inputs. Frozen source rechecked saved material and confirmed byte-identical JSON.
- Normal control was CPU/full SRAM/events exact; option-off control was CPU/events exact against the prior failure profile. This is not expanded to no effect from all observers or initial state of other firmware.

Under `~/Library/Application Support/Blackwall/simulator/` outside Git:

- `imu-initial-indirect-research-01/`: source manifest, C/H, previous model, check/frozen results and `manifest.json`.
- `imu-initial-ireg-red-01`, `imu-initial-ireg-green-01`: unit failure/5,051 passes.
- `imu-initial-ireg-main-01/{stock24,stock23,cfw}`, `imu-initial-ireg-nominal-01`, `imu-initial-ireg-off-01`.
- `imu-initial-ireg-*-plan-01.json`: actual run plans. `plan-02.json` is the semantic contract fixed at service boundary without changing execution settings.
- `imu-initial-ireg-audit-01/`: five audits without a new native run.

```sh
python3 tools/prepare_iom4_imu_candidate.py \
  "$HOME/Library/Application Support/Blackwall/simulator" <new-plan-json> \
  --current-startup --initial-ireg-ready --case stock24 --identity-byte 0

"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/verify_imu_identity_failure.py \
  "$HOME/Library/Application Support/Blackwall/simulator" <new-check-json> --initial-ireg
```

The option is a virtual state connecting source-supported transport and explicit responses; it does not verify physical ready, NACK, or GAF computation. Next examine a contract connecting actual IOM error responses to upper error handling/application lifetime. Normal GAF computation, initializer/wrapper return, and natural UI remain incomplete. bw351/bw357 incomplete status and overall 4/16=25%, API checklist 3/6 remain. No physical access, flash, or persistent writes occurred.
