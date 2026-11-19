# Natural M55 Integration of Two P-256 Events and 69-Byte Reception

bw-0295. Connected the [original asynchronous-event contract](p256-asynchronous-event-contract.md) to an optional virtual peer. No physical device access or installation occurred.

## Natural execution results

| Original main | Selected profile | Cumulative commands / response events | Next original request |
| --- | --- | --- | --- |
| Stock 2.4 | `test-generator` | 22 / 23 | `2017`, 36 bytes |
| Stock 2.3 | `test-generator` | 22 / 23 | `2017`, 36 bytes |
| Faceclaw | `test-generator` | 22 / 23 | `2017`, 36 bytes |
| Stock 2.4 | `test-error` | 22 / 23 | `2017`, 36 bytes |
| Stock 2.4 | New feature disabled | Existing 21 / 21 | Existing `2025`, four bytes |

The four active candidates recorded 51 CS frames, 102 IOM commands, and 20 application reply drains. Command `2025` returns Command Status and a separate LE completion event, so command and response counts differ. The next request stopped at the original write-ready GPIO check and was not actually transmitted. PCs were stock 2.4 `0x501676` and older stock/Faceclaw `0x549fce`.

All five runs were natural Renode M55 executions starting at original main reset. Original main bytes were not modified and PC/return registers were not forced. Existing virtual peripheral, initial-memory, and response assumptions continue to apply. This does not prove full ROM boot or physical hardware equivalence.

Connected R8/R9/R10 and the ring record in actual SRAM to identify the next request. The 36-byte requests in the four active runs matched the SHA-256 of results from earlier isolated original-function/WSF-owner tests. In the three normal runs, the 64-byte value with both coordinates converted to big-endian existed in actual SRAM and was absent from the earlier saved state. Do not extend this memory evidence to validity or security of a key store or completed pairing.

## Lifetime of the two events

`BlackwallEm9305EventPeer.p256PublicKeyProfile` is disabled by default and can be selected only with an explicit existing privacy profile.

- `test-generator`: returns a public fixed P-256 point, not a real controller key or secure random value.
- `test-error`: error test returning status 1 and zero-filled coordinates.

Consuming the first seven-byte Status does not complete the command. The subsequent 69-byte LE completion event remains in `ReplyQueued` and completion occurs at the second CS commit. The application RDY check distinguishes this explicit intermediate state from the final 23 response count. Unsupported commands, invalid payloads, short receives, wrong order, and automatic rearming after reset remain blocked.

The next `2017` also occurred after error completion. This is an observation of original code, not evidence of safe fallback, successful initialization, or verified security state.

## 69-byte reception and FIFO

Initial peer testing exposed the existing SPI model's 32-byte limit. A separate natural M55 preflight requested actual original `CMD=0x4502` at PC `0x582242`. The first Status was delivered, but strict blocking occurred before the second event's payload transfer. The raw semantic-failure capture was preserved and a separate saved audit confirmed only this partial progress. The same execution was not restarted due to a timeout.

After CMD write, original ARM reads receive size from FIFOPTR and repeatedly reads FIFOPOP. The blocking RX loop in the [pinned public Apollo510 HAL](https://github.com/zephyrproject-rtos/hal_ambiq/tree/61b293a49db34030c545f99101f7ebf6a3050314/mcu/apollo510/hal/mcu) works the same way. The guest function was not replaced with an SDK structure ABI.

Added optional `BlackwallStrictIom.spiReceiveStreaming`. It fills up to eight FIFO words in receive-only transactions and replenishes each slot after the guest pops it. Completion is signaled once after the last valid byte is received. Final-word padding is not included in the peer payload. Host TX FIFO clock supply during transfer is rejected. In the reset control during 69-byte reception, FIFO emptied and the peer remained `Exhausted`.

The default 32-byte limit and full-duplex transmit limit remain. The optional gate adds an exact peer-length contract check for receives up to 255 bytes. The newly verified long receive was 69 bytes. All other lengths, DMA, and actual clock/backpressure timing were not verified. FIFO replenishment is untimed virtual behavior.

## Verification and assets

- Confirmed a red failure requiring the unimplemented `p256PublicKeyProfile` constructor.
- The constructor rejected a length typo in the first public-point string. Native exit 133 and raw logs were preserved, and the input was corrected to the verified 64-byte original test vector.
- Passed 364 default two-event, 565 small transfer fragment/error-profile, 324 reset-during-long-receive, 333 feature-disabled, 58 existing two-command, and 50 existing SPI-word regression checks.
- Passed five final natural executions and five saved audits. One earlier partial preflight and its audit were preserved separately. Audits are not CPU reexecutions.
- Disabled control CPU state, instruction count, registers, and existing observation events exactly matched the prior baseline.
- Reanalyzed saved results with 46 pinned Python dependencies and confirmed byte-identical reports. Confirmed both models were actually reflected in compiled output and checked original main/full SRAM hashes.
- Changed peripherals were `renode-em9305-reset.cs` and `renode-iom.cs`. keyDB and OTA-marker model hashes were unchanged. The web installer, recovery boot, and installation CFW were not modified.

Tools are `tools/prepare_p256_candidate.py`, `tools/inspect_p256_profiles.py`, and the existing candidate runner. Case paths required by the source runner were connected using verified symlinks in private `p256-peer-source-01`. Earlier captures were not copied, moved, or overwritten.

The simulator's `p256-peer-verification-01/manifest.json` outside Git tracks models, dependencies, units, native runs, and audits. Final captures are `p256-peer-main-01/{stock24,stock23,cfw}`, `p256-peer-error-01/stock24`, and `p256-peer-control-01/stock24`. Partial failure remains at `p256-peer-preflight-01/stock24`.

Next verify exact AES input to `2017`, return consumption, and subsequent initialization/persistent-storage intent in original code, then continue the natural app/display path. Do not return arbitrary cryptographic results as success. Overall product completion remained scope v2, 13/29 = 44.8%. Normal boot, integrated display, and readiness for physical installation were incomplete.

Corrected dashboard S5 from `not started` to `partially complete`. This reflects only BLE initialization responses and connection to natural main. Input, sensors, and full interrupt/lifecycle remain incomplete; it does not mark S5 complete or change acceptance criteria.
