# Original Privacy and Data-Length Initialization Contract

bw-0292. Software analysis without accessing glasses or case. No new natural M55 execution was performed, and full boot, app loop, and display completion are not claimed.

## Starting state and execution scope

Used bw291 saved natural-main states for stock 2.4, stock 2.3, and Faceclaw. Verified all capture hashes from the existing audit and loaded full SRAM and original ARM binaries into Unicorn M7. Executed original ring pop → H4 parser → upper handler using synthetic stack, registers, and call entry. Original code was not modified and branches were not forced, but this isolated call is not equivalent to natural M55 execution.

Tool: `tools/inspect_privacy_length_contract.py`. Proprietary inputs and derived reports are preserved only in simulator directories outside Git.

## Confirmed sequence

| Request opcode | Explicit virtual response | Next original request |
| --- | --- | --- |
| `202a` | Status 0, resolving-list size 4 or 1 | `202f` |
| `202f` | Status 0, TX/RX maximum lengths and times | `2024` |
| `2024` | Status 0 | `2018` |
| `2018` calls 1–3 | Status 0, eight public test-vector bytes each time | `2018` |
| `2018` call 4 | Status 0, eight public test-vector bytes | HCI transmit queue empty |

The large profile uses TX/RX 251 bytes and 2,120 µs; the small profile uses 27 bytes and 328 µs. TX length and time in original-generated `2024` exactly matched the respective response values. The actual storage location and later use of resolving-list size are not established by these results alone.

LE Rand returns status and eight random bytes. A [distributed copy of Bluetooth SIG specification §7.8.23](https://community.infineon.com/gfawx74859/attachments/gfawx74859/psoc4/1318/3/Core_v4.2.pdf) was checked via its search index. Instead of actual randomness, hexadecimal `01..08`, `09..10`, `11..18`, and `19..20` were used. These are not secure random numbers, device secrets, or evidence of actual EM9305 behavior. The meaning of subsequently generated keys or security state was not yet established.

For each of three images × two profiles, seven completion responses—a total of 42 steps—were handled in the same order. Six controls that invoked only the handler after popping the first request, without a completion event, produced no subsequent request. All 138 synthetic function calls reached the return sentinel.

An empty transmit queue does not prove initialization completion, advertising start, or a normal app loop. Events, timers, callbacks from other tasks, and intent to persist data must be checked in the next natural execution. `202e` RPA timeout configuration did not appear in this actual follow-on path.

## Verification, constraints, and next work

- Final analysis: private `privacy-length-source-02/report.json`.
- Reanalysis with 41 pinned Python dependencies: private `privacy-length-source-03/report.json`, byte-identical to the final report.
- Verification assets: private `privacy-length-verification-01/manifest.json`.
- The first exploration tool assumed “there is always one next request,” which did not match the empty queue after the fourth Rand. It was fixed to observe an empty queue explicitly. No command was inserted to advance firmware execution.

Models and the web installer were unchanged. Contracts for wrong opcode, error status, and short return values were not verified here. Next add an opt-in model and tests allowing exactly the seven request/response pairs above, then observe subsequent natural M55 main behavior with the pinned candidate runner. Do not return success to arbitrary commands or provide test vectors as secure randomness.

Overall product completion remained scope v2, 13/29 = 44.8%. Readiness for physical installation/recovery and integrated display remained incomplete.
