# Plan to Connect Registered Candidates to the Communication Runtime

bw382, partial E15/E16 work. This executes the already approved emulator-only objective and bw380/381 transition. Connect the existing raw-main registry, memory policy, and device-input runtime without duplicating candidate validation or runners. The CLI explicitly specifies the manifest and the baseline used for registration.

- [x] Build accepts and validates a registered candidate and baseline and substitutes the actual main and length protection.
- [x] Compare runtime observation-code anchors with stock. Reject incorrect registrations before creating output or executing.
- [x] Freeze the registration manifest and baseline assets inside the capture for audit reuse. Do not require the registry again for audit.
- [x] Execute and compare the existing E04 marker candidate and stock in the actual ATT → app/RTC scenario under the same model and inputs.
- [x] Confirm rejection of candidate, baseline, and protection-policy mutations, audit historical captures, and check records/progress. Do not declare full E15/E16 completion.

New CFW product features, UI/sensor calculation reimplementation, and physical work are excluded. This validates the raw-candidate execution path of the hardware emulator. No Astra or other agent was used.

The regression candidate detected an app_state failure, but an unexpected four-byte SRAM difference remained, so the comparison failure was retained. Explaining its impact is follow-up work; this is not complete E15.
