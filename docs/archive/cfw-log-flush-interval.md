# CFW storage interval differences and log flush retry

Task bw-0223 traced 92 CFW storage events that differed in the [UART0/HCPA comparison](../hardware/communication/uart0-hcpa-status-model.md). These belong to the original EasyLogger asynchronous thread's `log/compress_manager.bin` path. Under the shared status profile, the log synchronization request had not disappeared: it remained **waiting for retry after a failed attempt**. The underlying reason for the first flush failure and whether a later retry succeeds remain unconfirmed.

## Original code and call path

The subjects are pinned Faceclaw38 ARM main and its stock 2.3.0.24 base. Compression service bytes at 43d000–43d840 and logger thread bytes at 44b52a–44b648 match across both images. The difference is therefore not explained as removal or replacement of code in this region by CFW.

The string at original 44b52a is `elog_async_handler_thread_handler start`. When bit 1 (value 2) of the event-wait return is set, 44b560 calls 43d534. At 43d570 it calls the actual flush operation at 43d45c. A separate function at 44b634 sends flag 2 to the same event object.

The stack frame was examined at the first post-FS callback in independent status mode. Comparing the 32-byte push and 24-byte local area of `lfs_file_opencfg` at 49a0c2, the direct-call return at 49a0fc, and the caller return at 49a35c shows the saved path argument is 79f549. The corresponding original string is `log/compress_manager.bin`. A code address on the stack alone does not establish general unwinding success; the call, layout, and argument of this particular file-open frame were checked.

Function names such as `lfs_file_opencfg` are reverse-engineering labels based on behavior, not extracted original symbols. The logger name and file path were confirmed in original strings.

The ICSR active vector at the observed filesystem callback and at both ends of the interval was 0. Those moments were in thread mode; they are not reported as observations in an IRQ handler. All times and states are from virtual execution.

## Request/completion numbers and retry state

The original uses the following state:

| Address | Original behavior confirmed |
| --- | --- |
| 20077684 | Request number incremented by 1 at 43d25a/25c on synchronization request |
| 20077688 | Completion number storing the target number on success at 43d3ae |
| 20077690 | Last-attempt tick updated at 43d388 after the kernel tick query at 43d384 |
| 20078427 | Retry counter incremented after the failure path at 43d3c8 |
| 20078426 | Retry-pending flag |
| 20078428 | Latch state after repeated failures |

43d4da–43d4f6 defers flushing and schedules the remaining wait if 5000 ticks have not elapsed since the last attempt. This is a code contract in 5000 kernel ticks; hardware tick frequency and real-time seconds were not measured in this investigation. Both tick getter paths read 20077e4c.

RAM read only after the existing strict stop, without new execution hooks, yielded:

| Item | CFW independent UART status | CFW HCPA status |
| --- | ---: | ---: |
| Request number | 3 | 3 |
| Completion number | 3 | 0 |
| Last attempt tick | 2923 | 2581 |
| Stop tick | 3370 | 3261 |
| Failure count | 0 | 1 |
| Retry pending | 0 | 1 |
| Latch | 0 | 0 |
| Post-FS read callbacks | 30 | 0 |

Request/completion numbers are not log message counts or byte counts. Under HCPA, last attempt 2581 was already recorded at the first filesystem initialization return, and completion remained 0 through GPIO sampling. Failure count 1 and pending 1 were confirmed by post-stop read. The 680 ticks elapsed by the stop are less than the 5000-tick retry interval. The request is pending, not classified as complete or permanently failed.

In the independent condition, 3/0 at initialization return changes to 3/3 at GPIO sampling, with 30 file reads and existing write-enable/status/write-disable events. HCPA remains 3/0 across the same interval. This difference corresponds to the originally recorded difference of 92 events. The first failure is not attributed definitively to filesystem readiness order or a particular lower-level error. Exact failure return location and cause, whether scheduled retry completes in later execution, and effects on actual NOR need further verification.

## Checking the effect of observation

Runtime observation used only the already registered PCs `LittleFS-app-init-return`, first `GPIO-role-sample-return`, and `LittleFS-read-entry`. The additional model only reads registers, bounded SRAM, and ICSR and stores host diagnostic state. Original code, PC, branches, returns, and peripheral responses were not changed.

Final `cfw-fs-interval-main-05/{independent,shared}` each match the corresponding existing `uart0-hcpa-main-02` in **all reported CPU/device state, instruction counts, and observed events**. This is not expanded to equivalence of all SRAM or all instruction paths.

Intermediate `main-03/shared` differed. Adding four new logger PC watches and runtime instruction-counter reads caused log work to be observed in an interval where it had not appeared before, and the equivalence check against the existing run failed. This result was excluded from evidence of the existing HCPA path. Whether the cause was a particular hook, counter getter, translation block boundary, or scheduling interaction was not isolated. Read-only observation is not assumed to have no execution effect. Its inputs, logs, and failure report were retained.

Investigation stages and reasons for reruns:

| Stage | Additional question | Treatment |
| --- | --- | --- |
| main-01 | First caller/path clues in 256-byte stack | Existing state/events matched in both conditions |
| main-02 | 768-byte frame and ICSR execution context | Both conditions matched |
| main-03 | New logger-internal PC and counter observations | Shared path changed; excluded from existing-path evidence |
| main-04 | Log state and event object using existing PCs only | Both conditions matched |
| main-05 | Additional retry/latch bytes after stop | Final both-condition match |
| log-paused-01 | Tick after stop without new execution hooks | Final both-condition match |

These stages did not repeat the same check without reason. They added distinct information about caller frame, execution context, observation effects, retry flags, and tick. The final audit used both main-05 conditions and both paused-only conditions. All 86 verification checks are in `simulator/cfw-log-interval-verification-01/report.json` outside Git.

## Post-stop SRAM inspection tool

`tools/inspect_paused_sram.py` was added. After checking pinned original main, input hashes, and existing logs, it replays the same run and reads only SRAM ranges after reaching the original strict stop. It adds no CPU code or hooks before or during execution. It then rechecks equality of CPU, instruction count, and existing events.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/inspect_paused_sram.py \
  "$HOME/Library/Application Support/Blackwall/simulator/uart0-hcpa-main-02/cfw" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-cfw-paused-inspection" \
  --range log-state:0x20077680:8 \
  --range log-flags:0x20078424:2 \
  --range kernel-tick:0x20077e4c:1
```

Addresses are source analysis values for this pinned original and must be rechecked before use with other versions. A new output path is required. Ranges are limited to aligned virtual SRAM 20000000–20380000, at most 256 words per range, and 1024 words/16 ranges total. Nine rejection cases for MMIO, out-of-range, invalid names, and lengths, and three valid-input cases were checked. The command's snapshot is not an actual device read. Proprietary originals and execution memory remain outside Git.

## Remaining goals

The CFW difference is characterized as pending/retry state of the stock log flush. Full trace equivalence, underlying cause of the first failure, and later retry completion remain unverified. The next implementation boundary is UART0 interrupt mask 40039038/1fd0. Normal font-bank, integrated app loop/display, and physical verification of web installation/recovery remain separately necessary. Overall progress is 13/29, 44.8%; there was no glasses access, installation, or persistent write.
