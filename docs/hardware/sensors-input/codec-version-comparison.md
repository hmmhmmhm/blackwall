# Comparing 2.3 and 2.4 Codec Payloads

Status: offline byte analysis of official distribution images. No codec execution, update, or physical device communication occurred.

Previously hash-verified official `stock-2.3.0.24.bin` and `stock-2.4.0.24.bin` were checked for component CRC and ranges with the project's `parse_bundle`, and type 4 payloads were extracted.

| Item | 2.3.0.24 | 2.4.0.24 |
| --- | ---: | ---: |
| Codec payload length | 326092 | 329092 |
| First four bytes | FWPK | FWPK |
| LE32 value at offset 4 | 0x203 | 0x204 |
| LE32 value at offset 8 | 2 | 2 |
| First section offset / length | 48 / 38236 | 48 / 38236 |
| First section zlib CRC32 | 0x307e8a10 | 0x307e8a10 |
| Second section offset / length | 38284 / 287808 | 38284 / 290808 |
| Second section zlib CRC32 | 0xc2da6c45 | 0x0150bf60 |

Interpreting 16-byte records from offset 16 as `(id, length, offset, crc)`, the two sections are contiguous and fill exactly to file end, with each CRC matching actual zlib CRC32. This supports the byte structure but is not confirmation of an official FWPK specification. 0x203/0x204 are not established as codec execution or protocol versions.

There are 236107 differing bytes over the common length, and the 2.4 file is 3000 bytes larger. Contents differ even excluding the first 32 payload bytes. Thus the hypothesis of identical binaries with only different headers is excluded. Matching first-section CRC alone does not establish cryptographic identity of that section.

`CMakeLists.txt:19` in the pinned open-research checkout comments that the codec is for GX8002B and byte-identical across versions. The cross-version identity statement does not hold for this input pair. The chip name is an upstream comment's claim, not hardware fact independently verified here.

These differences alone neither establish main-only installation failure nor compatibility. The next evidence is main's codec package check, transfer and version-negotiation paths, and the changed second section's role. Automatic codec downgrade or additional writes were not authorized.

## Section hashes and follow-up on main references

Full bundle hashes were repinned, and external component CRC and section zlib CRC32 checked. Results are preserved in private `boot-2-4-analysis/codec-partitions-01.json`.

| Section | 2.3 SHA256 | 2.4 SHA256 |
| --- | --- | --- |
| 1 | 393d2ae1f10ed1382f3eec6e3f9f9ac99d744b7ab41d0c89a003f96588afe391 | 393d2ae1f10ed1382f3eec6e3f9f9ac99d744b7ab41d0c89a003f96588afe391 |
| 2 | 60adadb83f3cc544c4f80729b01c20d5f94dc54dcbca254f7e7ca3f45b1b115f | 586377db58d8b7d494dfcaa23e5be2b8b036966cef75eef4755e065d38f38ecd |

The first section is identical through SHA256. Boot/application roles of the sections and codec protocol compatibility remain unconfirmed.

The main raw image was searched for `/firmware/codec.bin` and four-byte-aligned literal occurrences of its addresses. In 2.3, strings at 0x7ba6b4 and 0x7ba934 have literals at 0x592168 and 0x59710c; in 2.4, strings at 0x7ac3d0 and 0x7ac664 have literals at 0x48d7c4 and 0x599c64. Codec update success logs and the GX8002 driver name also exist. Literal occurrence alone does not prove an executable reference or call flow. `FWPKXUt` found by string search may be instruction bytes and is not treated as a meaningful log string.

## Limited execution of actual header-reading code

The 2.3 function at 0x596efe referencing `get_firmware_package_version` and corresponding 2.4 code at 0x599a56 were run with `tools/emulate_codec_header.py`. Only file open/read/close and log-enabled query were replaced with stubs. Actual filesystem and codec hardware were not executed.

Twenty cases passed: two mains × two codec headers × five conditions (normal, bad magic, short read, open failure, null output pointer). The normal path opens `/firmware/codec.bin`, reads 16 bytes, closes it, checks `FWPK`, and returns the offset 4 word. At this stage the 2.3 function reading 0x204 and the 2.4 function reading 0x203 are also allowed. Error paths returned −1 and left the output word unchanged.

The first test failed because open mode was conventionally assumed to be `rb`; the actual literal was `r+` in both versions. Input checks were corrected to that actual value and rerun. A function name indicating information lookup does not guarantee unchanged real-device file access. Here all file operations were memory stubs.

Results are private `boot-2-4-analysis/codec-header-readers-01.json`. This function reads a version value only; it does not check subsequent version comparison, update decision, or codec execution protocol compatibility. There is still no safety conclusion for main-only installation.

## Caller version comparison: update path on mismatch

Subsequent offline analysis found candidate BL instructions directly calling the reader at 2.3 `0x5989b6` and 2.4 `0x59b50e`. On success the package word is at stack+0x10, and a later comparison simply tests equality with stack+0x14. The query function populating stack+0x14 and actual codec communication had not yet been executed.

`tools/emulate_codec_decision.py` executes only the comparison region from actual binaries. Inputs are stock 2.3, stock 2.4, and Faceclaw/38 pinned by bundle SHA and component CRC. The corresponding Faceclaw region is identical to stock 2.3 through SHA256. This does not prove all Faceclaw codec behavior is identical.

| Image | Comparison start | Mismatch-path join | Equal-path epilogue |
| --- | --- | --- | --- |
| Stock 2.3 / Faceclaw38 | 0x598b70 | 0x598c2c | 0x598ce8 |
| Stock 2.4 | 0x59b6c8 | 0x59b784 | 0x59b840 |

Six conditions per image, 18 total, ran: `(0x203,0x203)`, `(0x204,0x204)`, mismatch in both directions, `(0x203,0)`, and `(0x203,0xffffffff)`. Equal values prepare result 1 and head to the epilogue. All unequal values head to the mismatch path. This region has no downgrade block based on magnitude or exclusion of 0/erased values. Protection at other stages is a separate question.

Branch-specific 2.3 literal logs include “no upgrade needed” for equality and “starting upgrade” for mismatch. The next call at the mismatch join is `0x5985f8`; the corresponding 2.4 call is `0x59b150`. The executor stops **before executing the join instruction**. Only log mask=0 is stubbed; actual version query, DFU, codec writes, and device behavior do not occur. Stack locals are explicitly supplied test fixtures. This test does not prove original caller entry, query value, force mode, file existence, or full boot flow.

Results and instruction traces are preserved outside Git in `recovery/boot-2-4-analysis/codec-version-decision-02.json`. Tampered comparison instructions were rejected by the pre-execution guard for all three inputs.

This evidence means **sending a main-only file cannot by itself be assumed to avoid codec writes after boot**. The value returned by the installed codec, NOR `/firmware/codec.bin`, and caller execution conditions must be checked. Current main-only Faceclaw installation is not declared safe and automatic codec downgrade is not permitted. The web installation gate remains.

```sh
python3 tools/emulate_codec_decision.py /private/verified-bundles \
  --output /private/reports/new-codec-decision.json
```

This tool requires an offline Python environment with Unicorn installed.

## Source and conversion of codec query response

The caller's stack+0x14 comparison value is populated as follows:

1. The 2.3 caller at `0x598a82` calls `0x59b094`; the 2.4 caller at `0x59b5da` calls `0x50361c`. The response output buffer is caller stack+0x18 and the second argument is 200.
2. The query wrapper passes register arguments `(2, 0x100, 0, 0)` and stack arguments `(0, response descriptor address, 200)` to a lower function. The time unit of 200 and actual wire-command encoding are unconfirmed.
3. If the successful response descriptor length at offset 18 is at least 4, four bytes are copied from the pointer at offset 14 to output. The query wrapper also writes those bytes to a separate RAM cache.
4. The caller converts the four bytes to a big-endian word at 2.3 `0x596ed6` or 2.4 `0x599a2e` and stores it at stack+0x14. This differs from the package header offset 4 LE32 read.

`tools/emulate_codec_query.py` executed the actual query wrapper and conversion function. Transport, descriptor initialization, cleanup, failure callback, and logging are explicit stubs. Eight conditions each for stock 2.3/2.4 and Faceclaw/38, 24 total, passed. They include three normal responses (00 00 02 03, 00 00 02 04, 01 02 03 04), success after two failures, continuous failure, lengths 3/0, and null output pointer.

- Normal responses converted to 0x203, 0x204, and 0x01020304 respectively.
- Continuous failure requested at most three times, invoked the failure callback once, and returned an error.
- Length 3/0 and null output returned −1 without changing four output bytes.
- Cleanup call counts corresponding to each request, including success and retries, were checked.
- The entire Faceclaw query wrapper region was identical to stock 2.3 through SHA256.

Results are outside Git in `recovery/boot-2-4-analysis/codec-query-01.json`. The lower transport creating actual response descriptors and the codec itself were not executed. Thus what an actual device returns among 0x203/0x204, the meaning of device identification/cache/error recovery, and packet integrity checking remain unknown. This test does not declare device querying safe.

Additional static observation: the 2.3 caller saves input r0; if its low byte is nonzero it skips query/comparison and takes the force path. An instruction in the query-failure branch also heads to the update join. Four BL candidates to 2.3 caller entry `0x598944` are `0x559472`, `0x5599c6`, `0x56e57a`, and `0x56e684`. Some pass 0; `0x5599c6` passes 0/1 according to input structure offset 8. These are static control-flow candidates and do not establish actual reachability or call frequency at boot. Next is limited execution of force/error paths and confirmation of upper-caller execution conditions.

```sh
python3 tools/emulate_codec_query.py /private/verified-bundles \
  --output /private/reports/new-codec-query.json
```

## Connected execution from entry through decision

`tools/emulate_codec_flow.py` starts at `0x598944` (stock 2.3/Faceclaw38) or `0x59b49c` (stock 2.4). Unlike earlier individual tests, it connects the caller to execute the actual header reader, query wrapper, and big-endian conversion function in order. Package headers come from the actual codec components of pinned bundles. Filesystem, lower query transport, memory initialization, mode control, string formatting, logging, response cleanup, and failure callback are stubs. Query responses are synthetic.

Nine conditions per image, 27 total, passed:

| Condition | Actual execution result | Query count |
| --- | --- | ---: |
| force=0, package and response versions equal | Function returned 1, stack restored | 1 |
| force=0, versions differ | Stopped immediately before update join | 1 |
| force=1, versions equal | Proceeded to update join without query/comparison | 0 |
| force=256, versions equal | Low byte is 0, normal comparison returned 1 | 1 |
| force=0, continuous query failure | Proceeded to update join after three requests | 3 |
| force=0, response length 3 | Proceeded to update join after query wrapper error return | 1 |
| force=0, file open failure | Returned −1, stack restored | 0 |
| force=1, file open failure | Returned −1 despite force | 0 |
| force=0, invalid FWPK magic | Returned −1, stack restored | 0 |

All update paths stopped before the first instruction at the join. Return paths executed through the actual function epilogue and return. Traces, calls, inputs, and results are preserved outside Git in `recovery/boot-2-4-analysis/codec-flow-01.json`.

The specific conclusion is: **if a verified file exists, this caller does not abandon the update merely because the codec version query failed.** Force input skips normal comparison but does not precede file reading and header checks. Since mode control is stubbed, success/failure and side effects of actual device mode changes were not verified. Upper-caller reachability and force generation conditions, actual filesystem state, transport/codec writes, and normal boot remain unverified. This result does not lift the main-only installation gate.

```sh
python3 tools/emulate_codec_flow.py /private/verified-bundles \
  --output /private/reports/new-codec-flow.json
```

## Upper caller candidates and input conditions

`tools/trace_codec_callers.py` decodes only candidates whose two halfwords have Thumb BL form and finds direct calls to the codec decision function. It checks each bundle SHA and component CRC and saves contextual instruction bytes and addresses. Data can decode as instructions and indirect calls/callbacks may be missed, so search results are not treated as a complete call graph.

| Code | Stock 2.3 / Faceclaw38 | Stock 2.4 |
| --- | --- | --- |
| BL in direct normal-check wrapper | 0x559472 | 0x57d3b6 |
| BL in input-structure-based force wrapper | 0x5599c6 | 0x57d90e |
| BL in state-handling region | 0x56e57a | 0x52ae7e |
| BL in initialization/state-branch wrapper | 0x56e684 | 0x52af88 |

Results are outside Git in `recovery/boot-2-4-analysis/codec-callers-01.json`. Faceclaw has the four direct-call candidates at the same positions as stock 2.3.

`tools/emulate_codec_callers.py` separately executed small wrappers. Actual selector/state getters return synthetic values and only memory initialization is stubbed. Execution stops **before** codec decision entry or subsequent behavior in another state. Seven conditions each for stock 2.3/2.4 and Faceclaw38, 21 total, passed.

| Wrapper input | Confirmed result |
| --- | --- |
| Direct normal-check wrapper | Decision function entry with force=0 |
| Input structure offset 8 word=0 | force=0 |
| Same word=1 or 0xffffffff | Normalized to force=1 |
| Upper selector return=1 | force=0 through direct normal-check wrapper |
| Selector return=0, state return=2 | force=0 through state wrapper |
| Selector return=0, state return=1 | Stopped before subsequent behavior in another state; decision function not entered |

The first test failed assuming the state wrapper initialized eight bytes in both versions. Actual 2.4 `0x52af6c` sets length 9. 2.3/Faceclaw remain at 8; tests were rerun after recording exact per-version lengths in the profile. This difference does not verify the rest of the state structure ABI or field meanings.

Execution results, instruction traces, stub addresses, and fixtures are preserved outside Git in `recovery/boot-2-4-analysis/codec-caller-execution-01.json`. Where offset 8 of this structure is populated and the actual meaning of selector/state values are unknown. The 0xffffffff test is synthetic input, not observation of erased settings on an actual device. It is not yet established whether these wrappers run during normal boot or OTA postprocessing. Thus this evidence is not generalized to “codec always updates at boot.”

```sh
python3 tools/trace_codec_callers.py /private/verified-bundles \
  --output /private/reports/new-codec-callers.json
python3 tools/emulate_codec_callers.py /private/verified-bundles \
  --output /private/reports/new-codec-caller-execution.json
```

Follow-up `bw-0020` is recorded in [upper entry path](codec-update-ingress.md). It adds limited execution including PC-relative function address registration and actual RAM getters. A defect was found in the existing tool's initialization stub: despite length validation it wrote only eight bytes. Therefore the 21 cases and length-profile explanation above are not interpreted as verifying exact nine-byte initialization on 2.4.
