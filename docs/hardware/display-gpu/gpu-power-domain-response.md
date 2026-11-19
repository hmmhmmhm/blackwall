# GPU power request and status response model

Status: 13 native synthetic conditions, four existing-behavior regressions, six normal main combinations, and stock 2.4 continuously-off path observed. This is not GPU engine, full boot, integrated screen, or physical power verification.

## Public evidence

Pinned Ambiq HAL `61b293a49db34030c545f99101f7ebf6a3050314` peripheral table assigns GPU request to PWRCTRL.DEVPWREN (0x40021004) bit 18 and status to DEVPWRSTATUS (0x40021008) bit 18. `am_hal_pwrctrl_periph_enable` sets the request bit after preparation and waits for status. It returns an error on timeout; the function does not guarantee request cancellation or power recovery.

## Explicit virtual response

`--gpu-power-response active|stuck-off` is selected with existing GPU preparation model and defaults off. On request before all 18 preparation stages is blocked. Request and status words are preserved separately; response without delay at first status read is an assumption.

- active: requested→on, request/status bit18=1.
- stuck-off: requested→stuck-off, request bit18=1/status=0.
- A request not yet answered on can be cancelled with write 0. Restart after cancellation is unsupported.
- Write 0 while on is blocked because separate GPU off preparation is unimplemented; it cannot bypass through the existing zero-write storage path.

Other peripheral/reserved bits, partial widths, and status writes are blocked. Other power domains have synthetic initial off state. Voltage, stabilization, power, reset propagation, and GPU commands are not modeled; on is current model's digital state, not equated with physical device power state.

## Verification and failure observations

Of 13 conditions in `gpu-response-native-guard-01/report.json`, six response-observation/idempotent-request/cancellation cases recorded completion sentinel. Seven for pre-preparation request, wrong bit, partial width, status write, on→off, and option disabled did not execute completion write after first unsupported access. `gpu-response-native-red-01/report.json` reproduced existing block as pre-addition failure evidence.

First stock 2.4 LP normal run `gpu-response-main-stock24-lp-01/report.json` reached request/status=0x40000, enable reads 8/status reads 8/write 1, phase=on, then stopped at PC0x560f68 attempting write 0 to GPU.INTERRUPTCTRL (0x400900f8). This offset was confirmed by compiled assertion of public GPU structure, not hardware verification or handling of register semantics.

`gpu-response-main-stock24-stuck-01/report.json` retained status=0/phase=stuck-off and progressed after 12 status reads to the same GPU register write. This synthetic-path observation cannot establish safe firmware stop or recovery on power failure. HAL error return and actual upper-caller handling are distinct. It is not evidence the same failure occurs on actual G2. Current GPU access stops at unsupported guard under either profile.

Synthetic request cancellation does not verify original firmware automatic rollback. Actual GPU power-off sequence and failure recovery remain incomplete.

## Remaining scope

First GPU register access is identified, but GPU initialization, command-list execution, interrupt, and framebuffer remain unimplemented. Python approximate runner's existing MPU boundary remains. No physical access, flash, OTA, MRAM changes, or external publication.

## Six original combinations

Six combinations in `gpu-response-main-comparison-01/report.json`—two stock versions and Faceclaw × LP/HP—reached the same register boundary with GPU request/status=0x40000, enable reads 8/status reads 8/write 1. Stock 2.3/CFW PC=0x530054, stock 2.4 PC=0x560f68. First stock 2.4 LP native result was reused after source/hash/option verification.

Comparison checks native 18 preparation stages, seven control fields, power response, and actual first GPU register write. Python SHCSR/MPU stop differs; extra cache sweep, buck reads 3, MCU reads 4, MISC controls 2, and clock read 1 are explicitly distinguished.

`gpu-response-source-audit-01/report.json` confirms pinned public-file hashes, EN/STATUS bits, compiled PWRCTRL EN/STATUS and GPU.INTERRUPTCTRL offsets, and existence of HAL request/poll/error operations. It is not automated proof of all HAL semantics or GPU behavior.

## Regression and reproduction

`gpu-response-native-regression-01/report.json` passed four default-guard, existing no-ack clock, HFRC force, and completed power-preparation cases plus one optional-null comparison regression. Missing prerequisite preparation option was rejected before input-file read. Related logs and actual GPU-access vicinity code for three inputs are preserved in `gpu-response-verification-01/`.

```sh
python tools/compare_dcache_startup.py <private-inputs> <new-private-output> \
  --buck-response active --mcu-clock-response nominal --gfx-power-storage \
  --hfrc-force-control --gpu-power-preparation --gpu-power-response active
```

For continuously-off profile use `--gpu-power-response stuck-off` in native runner. Actual failure-path observation here is one stock 2.4 LP combination; failure recovery for other images/combinations remains unverified.
