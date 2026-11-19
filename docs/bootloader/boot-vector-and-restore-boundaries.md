Follow-up: [full main restoration and interrupted reset](full-main-restore-results.md) brings current progress to 7/12=58.3%. The 5/12 below records this document's initial verification history.

# Boot vector, virtual MRAM, and restoration boundaries

2026-11-17 · bw-0560/0561/0562. BV03/BV09 of the [12 bootloader conditions](bootloader-validation-plan.md) were completed within declared test scope. Overall was **5/12=41.7%**; full recovery and physical safety certification remain incomplete.

## Original SP check: bit 29 on the no-update handoff path

Pinned stock 2.4 boot SHA ecb91896… at 42e3fc–42e402 reads the selected main's first word, shifts left two bits, then branches with BPL. This SP gate checks bit 29 of the original value. It does not validate the full SRAM range or eight-byte alignment. Do not generalize this to absence of checks in preceding message selection or other update paths.

`verify_boot_sp_predicate.py` executed original LDR/LDR/LSLS/BPL as actual ARM instructions for nine synthetic SPs. Boot code was readonly with no MMIO/function stubs/forced branches. This is an isolated function interval test with only an end observer. All traces matched the same four instructions→accepted/rejected target, and results matched SP bit 29.

Two additional M55 full resets observed the same original branch:

| SP fixture | Actual branch/subsequent behavior |
| --- | --- |
| dead0000 | Raw value observed at sp-predicate → original rejected target 42e1f6, handoff/main 0. Subsequent idle CPD request e001e300=22 remains an unsupported boundary |
| a007fb00 | Bit 29 is 1, so accepted 42e406 → stock handoff → main reset. Actual PSP=a007fb00 and CONTROL 2 passed into main entry |

Both confirmed guest boot/main bytes unchanged for fixture input, fault/policy violation 0, and no missed observations. Main entry with SP outside SRAM is **not boot safety or complete main-operation success**. Subsequent main-reset initialization may change banks, so absence of immediate fault does not establish a valid SP.

The existing reset 90000001 test has handoff 1, main-reset 0, CFSR 1/HFSR 40000000. Thus original branch, guest fault, and model unsupported behavior were distinguished for declared invalid SP/reset inputs. This does not claim every boot vector combination is safely rejected. BV03 completes this decision capability and pinned cases.

Evidence: private `boot-sp-predicate-bw560-01.json`, `boot-sp-audit-bw560-01/report.json` (20 conditions), `boot-validation-{invalid-sp-diagnostic,sp-bit29-outside}-bw560-01`, and existing invalid-reset capture. Proprietary boot bytes remain outside Git.

## Forbidden virtual MRAM writes and atomic rejection

Follow-up correction (bw-0563): the API test below alone did not prevent direct CPU writes. An actual M55 STR changed four bytes, reopening BV09; completion was restored only after confirming actual write-boundary blocking, six direct stores, and four existing ARM regressions in the [separate protection fix](../hardware/cpu-memory/mram-direct-store-protection.md). The following results are pre-fix API-boundary history.

`BlackwallRecoveryWriterFixture.Program` request checks were grouped in `ValidProgramRequest`. This policy authorizes the **existing isolated fixture testing 512 bytes from main body 438010**, not an actual silicon ROM permission table. Default range, ABI, ROM status, and recording method remain.

- Pure C# 23 conditions: normal 16/256-byte and end boundaries, invalid key/operation, boot/main vector/metadata/out-of-range destination, word count/overflow, source SRAM range/overflow, IRQ mask, and allowed-range setup.
- Eight invalid requests to actual `Program` method: synthetic CPU register/stack values were first checked against inputs, then method directly called. Expected CpuAbortException and exact rejection reason were confirmed. All 4 MiB MRAM matched before/after; ROM calls 0, programmed bytes 0, destination/length lists 0, no RESULT/stop flag.
- These eight are **C# component tests without guest ARM execution**. The difference between AddHook exceptions and direct host calls is not hidden. They do not verify every direct store by a running invalid guest or host crash behavior.
- Four actual M55 regressions passed: compiled context wrapper→RAM writer/callback→stock MRAM adapter under normal, ROM status 7, readback mismatch, and 272-byte interruption. Earlier four interruption/four retry evidence was also retained.

Full MRAM SHA for the four regressions was independently reconstructed from retained 512-byte body and original baseline; boot/vector/metadata/neighbors were unchanged. Under given states forbidden requests are rejected before recording, and supported success/error/interruption changes match expected ranges. BV09 completes this virtual policy/pinned scenario; actual partial-bit programming, power collapse, and ROM security settings remain unverified.

Evidence: private `mram-boundary-{red,green}-bw561-01`, `mram-boundary-atomic-bw561-02` (23+8 conditions), `mram-boundary-replay-bw561-01/{summary,audit}.json` (16 conditions). The first atomic component test lacked later register/stack and rejection-reason checks, so final 02 is acceptance evidence. All model/execution source/logs remain. Duplicate regression MRAM/SRAM totaling 35,651,584 bytes was cleaned up after verification.

## Full-stock cannot be determined from boot-prefix hash alone

The new restore checker incorporates the existing `audit_assets.py` finding that appended-page originals are needed. Declaring full-stock bytes true from named SHAs and `inventory_complete=true` alone was insufficient. It now also requires coverage of known original address ranges and actual changed ranges. Old hash-only inputs remain readable but yield full-stock=false without coverage.

`check_virtual_restore.py` accepts typed address-space/address/bytes extents and computes overlap. Different devices/memory spaces, one-byte gaps, and append areas outside the stock prefix are not considered covered. Source legitimacy, completeness of write journal, and actual reboot need separate evidence; this checker always retains reboot_verified/hardware_validated/installable=false.

Pinned official bundle SHA and component CRC were rechecked to establish ranges:

| Version | Official boot payload | Outside official payload within 159744-byte patch footprint |
| --- | ---: | --- |
| 2.3.2.14 | 149760 bytes, end 434900 | 9984 bytes, 434900–437000 |
| 2.4.0.24 | 149773 bytes, end 43490d | 9971 bytes, 43490d–437000 |

This is the difference between an **assumed patch transfer footprint** and official payload length. Payload length alone does not prove the full range actually changed by OTA. Original values in those areas are not assumed to be 0xff. A virtual full restoration test must preserve those bytes from the pre-modification virtual MRAM snapshot as original assets. Physical full-stock certification separately needs legitimate original/range evidence for that device.

A virtual prefix-only restore with both official prefix/main hashes matching was rejected as full-stock=false because append area was unknown. Ten host tests passed, including retained tail backup completing coverage and a one-byte gap remaining. This is checker counterexample verification, not an actual restoration result.

There is another constraint: existing 2.4 writer RAM API callbacks `send_output434d24`, `recv_input434dc4`, and context wrapper 434910 lie in patched boot append. Restoring that area may overwrite current service code/return path. Main and full boot restoration are not treated as the same operation. Where communication/return breaks with the existing writer remains for later virtual execution, with success/failure not yet established by execution.

Evidence: private `stock-restore-extents-bw562-01/{report.json,host-tests.log}`, existing offline asset audit, and each patch's metadata. Source changes were limited to checker/model/tests/docs; boot patch itself and upstream allowlist were unchanged. No physical device, external posting, or subagent execution occurred.
