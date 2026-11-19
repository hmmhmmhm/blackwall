# Upper Entry Path to the Codec Check

Work `bw-0020` provides partial evidence for overall completion condition F4. No hardware access occurred. The 27 connected tests and 21 wrapper tests from the existing [codec comparison](codec-version-comparison.md) were reused, and the upper path unexplained by direct-call searches was investigated.

## Newly established scope

Original ARM code from stock 2.3.0.24, 2.4.0.24, and Faceclaw38, with pinned bundle hashes and CRCs checked, was executed in a limited manner using `tools/emulate_codec_ingress.py`.

| Boundary | Stock 2.3 / Faceclaw38 | Stock 2.4 |
| --- | --- | --- |
| Address registration region start | 0x5592a8 | 0x57d1ec |
| Candidate creation function stopped before execution | 0x442896 | 0x4427f2 |
| Thumb function pointer calculated in R0 | 0x559491 | 0x57d3d5 |
| Function start | 0x559490 | 0x57d3d4 |
| Byte read by selector getter | 0x200046e9 | 0x200069f5 |
| Byte read by state getter | 0x200784db | 0x20077d6c |
| Stubbed preparation service | 0x4e3734 | 0x4ede02 |
| Stub initialization length | 8 | 9 |

The registration region calculates the pointer with PC-relative `addw` and passes it with R1=0 to the candidate creation function. All three images stopped before executing its first instruction. Function creation, scheduling, and reachability in normal boot were not established.

At the upper function entry, all 16 combinations of selector/state bytes 0, 1, 2, and 255 were run for each image. Actual RAM getter code executed. If selector=1, or selector≠1 and state=2, execution stopped immediately before entering the codec check with force=0. Others stopped before subsequent behavior in another state. Forty-eight combinations met these limited conditions; with three creation boundaries the total is 51.

The preparation service is a stub checking argument 3 and returning without side effects. Initialization at 0x43c0e4 is also a zero-fill stub of exact length. SRAM was filled with 0xa5 and the four bytes before and after the initialization region were verified preserved. ROM permits read/execute, SRAM read/write only. Execution outside allowed code ranges and guest writes outside stack/initialization regions stop. Files, transport, and codec updates are not executed.

## Failed execution and remaining limits

Initially the original initialization function was executed. With stock 2.3 selector=0/state=2, it took another state branch instead of the expected codec entry. The trace did not show the state getter call instruction after initialization. The condition was reproduced and failure material preserved. Whether the cause is the CPU executor or something else is undetermined and is not interpreted as real-device behavior. The 48 cases above are results after isolating initialization with a stub.

A defect was also found in the earlier wrapper tool's initialization stub: it used `bytes(8)` despite checking version-specific length. The existing 21 cases are not evidence for 2.4's nine-byte initialization. The new tool checks exact length and guards, but correction and regression verification of the old tool remained.

Unknowns include the producer of force input structure offset 8, actual preparation service side effects, selector/state meaning and actual boot values, identity and upper caller of the creation function, and NOR/codec write scope and recovery after update. F4 is partially complete; installation permission and overall progress are unchanged.

## Evidence and reproduction

`simulator/codec-ingress-01/report.json` outside Git preserves traces, writes, stub calls, initialization guards, and image hashes for 51 cases. Failure is `original-memset-failure.json` in the same folder. The base path is `~/Library/Application Support/Blackwall/`.

```sh
python3 tools/emulate_codec_ingress.py /private/verified-bundles \
  --output /private/reports/new-codec-ingress.json
```

Reuse existing completed inputs. If rerunning is needed, first record the reason in the work log.

Follow-up `bw-0022`: [executor cross-check](codec-execution-backend-comparison.md) reproduced the association between the Unicorn write hook and mismatch, and verified 12 conditions on the original native M55 path with monitoring retained. The existing stub's 8/9-byte error was also corrected with a regression test. The statement above that correction/regression remained describes the earlier state. The Unicorn original connected path itself remains unresolved, and the verification scope of the existing 48 stub-based conditions is unchanged.
