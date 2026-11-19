# Separating Candidate Execution and Semantic Verification

Follow-up bw265 added optional schema 2 [post-stop SRAM/ITCM export](original-main-full-memory.md). Existing plans continue to work; saved audits also check export lengths and native/host hashes.

bw-0239 added schema 2 plans and saved-run re-audits to `tools/run_native_candidate.py`. Original ARM, models, and runtime observations were unchanged. This common tool reduces fragmentation of new-candidate behavior judgments across private audit scripts.

## Verdicts

Schema 2 requires candidate and control contracts for every input. The entire contract is checked before execution; missing fields, unknown comparison policies, and empty check lists are rejected.

- `execution_passed`: pinned inputs and log/stop-format validation succeeded.
- `semantic_validation.passed`: all expected plan behavior matched.
- `passed`: under schema 2 both verdicts must pass for true. Semantic failures preserve results and exit 1.

Existing schema 1 retains the old `passed` meaning of execution success for compatibility, but is marked `semantic_validation.passed=null`, `status=legacy-capture-only`. A schema 1 true is not reported as passing semantic verification. New candidates use schema 2; historical plans/reports were not bulk modified.

## Contract structure

`semantics.<case>.candidate` and `.control` have:

| Field | Content |
| --- | --- |
| boundary | strict-mmio checks PC, address, operation, width, value, and single access. bounded-capture/system-control limit scope through type and separate checks |
| comparison | exact, prefix, and subsequence compare specified JSON paths with baseline. bounded-invariants compares only explicit paths and does not mean full CPU equivalence |
| checks | Compare JSON path against eq expected value or eq_source baseline path. Missing paths and bool/int confusion fail |
| allowed_differences | Description of permitted differences; the description itself is not an exception ignoring failed checks |
| unresolved_differences | Remaining differences such as physical timing or unverified behavior, preserved even in passing reports |

Event loss and sequence mismatch are rejected separately from comparison policy. Existing control CPU/observation agreement or bounded control checks remain.

Example `tools/gpio-unchanged-contract-candidate.json` retains existing GPIO run configuration and adds only contracts. It distinguishes stock 2.3's 0x8e80 from 0xe80 in the others and checks GPIO state, original pad configuration, UART bytes, IRQs, and touch/role reads. This plan is not a new firmware image.

## Saved-run re-audit

```sh
blackwall_sim="$HOME/Library/Application Support/Blackwall/simulator"
python3 tools/run_native_candidate.py "$blackwall_sim" \
  tools/gpio-unchanged-contract-candidate.json \
  "$blackwall_sim/gpio-unchanged-main-01/stock23" \
  --case stock23 --audit-existing \
  --audit-output "$blackwall_sim/my-new-contract-audit"
```

The result folder must be a new path. Existing capture file SHA, pinned main, plan, runner, and actual CPU/observation/diagnostic logs are compared. Changes other than schema/semantics in the existing run plan are not allowed. Baseline observations are also compared with saved logs. Past inputs are not regenerated with the current component builder or latest model.

Contract plan, audit runner, helper dependency files/hashes, capture/source hashes, and verdict are preserved in separate audit output. Original capture is unchanged. This option runs neither Docker nor a device. Re-audit of the same saved run using only preserved runner and helpers was confirmed.

## Verification and limits

After a failing test established missing functionality, 11 unit tests passed. Fifty-two host checks in private `simulator/native-contract-verification-04/report.json` also passed.

- Common contracts passed for three actual saved mains and stock 2.4 control.
- Wrong expected PC/value/address/width recorded exit 1 and semantic failure.
- Changed execution plans and missing per-input contracts were rejected before audit creation.
- Host replay replacing only execution calls with saved log returns tested actual runner file assembly and result judgment: schema 2 success/failure, control, and schema 1 compatibility. This is not new native execution.
- First independent execution of the frozen runner failed due to a missing indirect helper dependency. Independent re-audit passed with that file included in the final preserved copy.
- Before/after SHAs matched for every baseline and existing capture file.

No new Renode execution or glasses access occurred. Existing native evidence was checked under a new common contract. This does not automatically establish physical validity of plan expectations; evidence review is required. Full boot, integrated display, and physical installation/recovery remain incomplete; overall stays 13/29=44.8%.

Follow-up bw242: boundary operations compare source-recorded named guard reasons exactly in addition to read/write. `cq-external-flags-unknown` is not substituted with read. Twelve unit tests including ordinary read/write contracts passed.

# Separate Approval of Saved Sources

Follow-up bw243: if a raw capture succeeded in execution but failed frontier expectations at the time, `reviewed_sources[case]` may explicitly contain `{ "path": "audit/report.json", "sha256": "pinned SHA256" }`. The path must be inside the private simulator. Runner checks execution_passed, audit/target agreement, all capture/source file pins, saved CPU/event logs, and audit contract re-evaluation. Approval reference remains in the new derived manifest's `reviewed_source_acceptance`. The raw report is not modified and passed conditions are not simply ignored. Existing passed-source paths remain.

Follow-up bw275: if a reviewed-source capture's plan declares memory export, those export files are included in capture pins and checked against raw report sizes/hashes. Next candidate runtime removes the source plan's exact exporter and replaces it with one new exporter. Unknown exporters or duplicate source blocks are rejected. A historical native issue producing two identical guarded exporter outputs is interpreted in separate audit only when exactly two blocks, identical records, and actual export hashes match. Different values or mismatched block/record counts are rejected. [First read transfer record](../hardware/communication/em9305-first-read-command-transport.md) preserves zero-capture restoration without restart and regression evidence.
