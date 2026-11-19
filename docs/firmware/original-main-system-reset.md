# Virtual system reset during original main execution

bw-0415. After the stock 2.4.0.24 original main handled a virtual phone's ATT time message, an external virtual NVIC SYSRESETREQ input caused it to re-enter the actual reset vector. The host did not set PC/SP or modify original branches or instructions. **E06, return to app state, remains partially complete**; the overall result is 8/16=50.0%, with the display checklist at 3/6.

## Execution results

The `runtime-att-acceptance-native-01/stock24` input from fixed E13 evidence was used. Its parent manifest SHA256 `a139c04c4c277f183d9ef9a8f7ab612bd3cc59cc5ed2beb6cfc9cbe7cca6fa3c` and child capture/input hashes were checked and cloned. Main SHA256 `df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a` remains unchanged. The existing main reset→virtual connection→ATT→actual TPL consumption/RTC update path runs without an API caller.

Board changes comprise the [separate NVIC reset model](../research/system-reset-boundary-contract.md), permanent initial vector configuration, and a reset-entry observer that removes only its own callback. Existing peripheral Reset implementations were not changed.

| Boundary | Actual observation |
| --- | --- |
| Before reset | Original consumer return `0x492ce2`, RTC commit 1, controller commands 59 and received events 3, fault/guard 0 |
| Input | External virtual bus writes `0x05fa0004` to NVIC AIRCR `0xe000ed0c`; the original firmware did not request this reset itself |
| Reset entry | Original vector `0x5fbe3e`, original initial SP `0x2007fb00`, VTOR `0x438000`, NVIC reset count 1, BASEPRI 0 |
| After 20 ms of initialization | Original zero-init loop `0x60bad8`, architectural fault/guard 0 |
| Longer initialization | Approximately 6.19 seconds after reset entry, the PPB guard stops at `str r1,[r0]` at `0x4956e2` |

The stop address is `CPDLPSTATE 0xe001e300`. Original literals and instructions and saved stack bytes `[0,2,2]` establish the write value `0x22`. This value was derived from fixed ARM data flow, not a direct register sample. The current normal-sleep model permits 0 and 0x11. The same unsupported value appeared in the earlier [new main reread after saving](../hardware/cpu-memory/kvtime-persistent-restart.md); this run confirms reaching that boundary after a **reset during execution on the same machine**. The guard was not relaxed and power checks were not bypassed.

## State lifetime and limitations

| State | Evidence and declarations for this run |
| --- | --- |
| KV/NV NOR backing | Entire 256 KiB hash matched before reset, at entry, and at the first 20 ms. It changed during subsequent original initialization, so final immutability is not claimed. |
| LittleFS NOR | Only source evidence that backing Reset is a no-op. The complete LittleFS bytes were not compared in this run. |
| ITCM | Full hash matched before reset, at entry, and at 20 ms. Existing memory policy written24 also remains; whether the new main recopies that code requires separate observation. |
| SRAM | 204 bytes differed between before the request and entry. This includes 28.6 µs of existing code execution between asynchronous reset request and entry, so it is not used to determine preservation or loss by reset itself. |
| RTC | Returns to the 2000 epoch and resets commit count to 0 according to the existing Reset implementation. Physical warm-reset retention is unverified. |
| Controller/PIO | Peer resets to Unreleased with 0 commands/events. PIO was idle both before and after at the selected points; this is not evidence of reset during a write. |
| Manual helpers | Memory policy and coherent-cache helper are not registered for automatic reset. Retained diagnostic history is distinguished from a claim that hardware state persists. |

The fixed infrastructure's [MappedMemory.Reset](https://github.com/renode/renode-infrastructure/blob/cd4b002aac2398994c4a61a34a8b31b5700facf2/src/Emulator/Main/Peripherals/Memory/MappedMemory.cs) does not clear contents. This alone does not establish that SRAM is identical before the request and at original entry. A preservation decision requires atomic before/after observations at a reset boundary with the CPU stopped.

## Verification and tool errors

Seventeen original reset/20 ms audit checks in `native-04` and 25 additional SRAM/NOR and long-run boundary checks in `native-06` passed. These are limited boundary audits, not an app-return pass. Counterexamples changing SP and expected SP together, NOR loss, and reset counter changes were rejected. Fourteen progress-management checks also passed.

Initial failures were retained outside Git. `native-01` had a callback delegate type compile error; `native-02` had a collector error that mistook variable e reused by existing run.py for emulation. In `native-03`, an entry hook paused the machine during RunFor, leaving the host waiting for completion time. After checking logs and container CPU/stopped state, only that container was terminated and exit 139 retained. The method was then changed to StartAll with bounded polling. `native-05` had a collector error looking for @none backing by sysbus path; it was corrected to use the existing owner path. None of these were counted as successful reset evidence.

Reverification uses saved results:

```sh
python3 tools/verify_original_system_reset.py <private-capture> <new-audit-directory>
```

Evidence is in private `simulator/original-system-reset-research-01/manifest.json`, `original-system-reset-native-04`, and `original-system-reset-native-06`. There was no physical device access or write, Astra/subagent, or external posting.

## Next work

Compare the original `0x22` CPU power configuration with the existing 0x11 contract and model the necessary power, sleep, and resume behavior. Do not simply allow the write to make it pass. Then verify cache/ITCM provenance and RTC/NOR retention rules across reset lifetime; E06 completion can be considered only after original service reinitialization→virtual connection→app event reprocessing returns. The same scenario must also be separately verified for other originals and new CFW.
