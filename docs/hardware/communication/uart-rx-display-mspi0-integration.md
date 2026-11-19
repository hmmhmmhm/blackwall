# UART RX → MSPI0 status check → original UI delivery

bw366, E05/E09/E13/E14. The stop address from the previous RX test's normal response was identified, and an already verified MSPI0/JBD model optionally reused. No new C# device model, firmware modification, or physical device access occurred. Normal receive paths in three originals reached the receive return point after UI producer invocation and pending-request release.

## Cause correction and reuse

Bw364 incorrectly interpreted diagnostic name `guard_iom7_tail` as a device name. IOM7 base is 40057000; stop address 40060000 is MSPI0. Access in the broad guard region was first forwarded to the MSPI0 owner and, on rejection, recorded under the guard name. The historical IOM7 work record remains, while current documentation and next-work guidance are corrected.

The basic MSPI0 transfer model already existed, but received bytes for JBD commands 05/35 were unspecified. The existing [JBD status consumption contract](../display-gpu/jbd-display-status-and-render-task.md)'s 1554 source scenarios, 68 model/45 TX checks, and native material were reused. Current `renode-mspi1-config.cs` SHA `109a4b8fc2dd0f1ed1ad0a96ef43bd551af4e77c1db7edce11ee3d91dc3efc9b` matches the model SHA in that verification manifest. Existing source report SHA was also compared. Those past tests are not counted as newly executed.

Only when explicitly supplied `--jbd-status-hex`, the runner replaces the frozen MSPI component with that verified version. It saves before/after source and SHAs and checks that model bytes outside the UART+MSPI components match. Main and initial SRAM/ITCM are preserved. A status profile is added only to the board's MSPI0 entry. Status bytes 5a01/9001 are virtual test inputs, not actual JBD reset values or physical state.

## Confirmed normal causality

The API test caller creates request, ID, and pending record through original allocator/start/chunk/finish, then waits via original queue API. Responses enter only through UART FIFO. Original ISR→uart_sync_thread→receive/parser code and scheduling are used. The host does not call receive callbacks/UI producer or force receive task/stack/IRQ mask. Because initial API caller injection remains, this is not classified as successful natural main integration.

Input stream is a 12-byte CRC error plus a valid 12-byte frame with the same request ID. Status 2 in the valid frame is a response passing the already sent app/payload to UI, not independent new UI content. Actual original UI producer entry showed app 10b, payload=original allocated packet+8, length 0, original receive TCB, and Thread mode. Request ID was removed from pending and parser reset to initial state.

MSPI0 consumed original commands 05 and 35 through actual FIFO reads. In the 5a01 profile, status frame order and payload/control matched, with complete receive and equal read counts. Finally execution stopped just before receive pop in the original uart_sync_thread, confirming entry SP and 16-byte prologue difference. This is **reaching the return point**, not a claim of complete task return after pop or full app operation.

| Run | Native result | Current saved audit |
| --- | --- | --- |
| stock24, 5a01 | Initial 26 judgments passed | 29 passed including UI arguments, pending removal, parser reset, MSPI order |
| stock23, 5a01 | 29 passed | 29 passed |
| Faceclaw38, 5a01 | 29 passed | 29 passed |

All three originals had CPU fault/unsupported access 0, and actual RX 24-byte order hash, IRQ vector 31, SRAM receive buffer, original task, and stack were confirmed. Final UI queue count was 0. Because UI can consume messages, final queue count is not used as an oracle for UI delivery; actual producer-call arguments/context and request pending state are checked. Observer neutrality is not established.

## Error controls under the same execution conditions

With stock24 5a01, sending two error frames yields UI producer calls 0, status 05/35 requests 0, pending request preserved, and parser reset. All 29 judgments passed. Strict/main/fill/board/probe/observer/runtime/harness binaries matched the normal stream byte for byte; only scenario differed within the profile. Changing only response in the same model distinguishes normal reply's UI causality. Three semantic checks separately reject incorrect UI payload, status bytes, and pending ID even when observation fields and source hashes are changed consistently. These negative cases are synthetic mutations, not new ARM runs.

With stock24 9001, the normal reply was followed by reading 90 at 05 and no 35 request. Then displaydrv_mgr_task attempted a 40020080 write at PC 5c1e6e and strictly stopped. The address is in GPU power region and matches the recovery boundary in existing status-failure diagnosis. There was no CPU fault, but receive return, pending release, and parser reset were incomplete. The native overall failure was retained as-is, not counted as recovery success or full E14 completion.

## Reproduction

```sh
<private-python> tools/run_sync_transport_m55.py <simulator> <new-output> \
  --case stock24 --scenario uart-rx-crc-then-valid --jbd-status-hex 5a01
<private-python> tools/run_sync_transport_m55.py <simulator> <existing-output> \
  --case stock24 --scenario uart-rx-crc-then-valid --jbd-status-hex 5a01 \
  --audit-existing --audit-output <new-audit>
```

The error control at the same status is `uart-rx-crc-pair`; the status-failure control is 9001. Existing default leaves status unspecified and preserves prior strict rejection. Saved audits verify capture/input hashes, raw JSON/log, and two component substitutions from the original model without rerunning the builder. Five malformed-profile/non-RX scenarios were rejected before output creation. Initial system Python failed import due to missing Unicorn; the verified private venv was used on rerun.

Nine existing native TX/CRC/RX captures and 183 judgments passed saved audit with the current checker. Fourteen progress-management tests passed. The private `simulator/uart0-rx-jbd-research-01` manifest and frozen runner preserve source, checks, matched controls, and boundaries. Proprietary main/SRAM remains outside Git.

## Next scope and limitations

All E01–E16 acceptance criteria, completion states, and denominator are unchanged. 4/16=25.0% and API display checklist 3/6 remain. This completion is original RX/UI integration for the declared 24-byte burst. Remaining work includes standalone 12-byte/split-input timeout, actual first app event→original request production, normal GAF service/initialization, natural main→full 576×288 frame, peer disconnect/delay, and all recovery. This test alone does not identify UART0's physical peer role as phone, opposite temple, or case.

Next is the actual root input and request-producer contract in [bw365 gate B](../../architecture/emulator-scope-audit-bw365.md). Do not indefinitely expand detailed functionality of the same path or add GPU recovery as a prerequisite for normal receive completion. The current 9001 failure boundary remains an explicit blocker for subsequent failure/recovery scenarios.
