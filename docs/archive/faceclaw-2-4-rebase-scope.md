# Scope of Faceclaw support for 2.4

Recorded 2026-11-10. This is offline research into retaining the current device version 2.4.0.24. No supported profile, relocated patches, or installation image have been created. Follow the user's choice when they answer about the base version.

Subsequent evidence: in [Faceclaw issue #56](https://github.com/jimrandomh/faceclaw/issues/56), the author says the downgrade path from 2.4.0.24 to current Faceclaw is supported. The following is therefore research into an alternative when retaining 2.4 is necessary, not required initial implementation scope. That statement does not verify mixed compatibility with a separate recovery boot or recovery of the user's device.

## Originals and comparison method

The 114 guards in upstream g2flash `845f665e0dfdcfd06b7d3a294388de6f17a5bd59` `stock_abi_230.json` were used. Full bundle SHAs for 2.3.0.24 and 2.4.0.24 were checked first; byte anchors were searched only within each Apollo raw main excluding its main preamble. Every existing guard was also checked for an actual match in the old original.

The [candidate report](../data/faceclaw-main-anchor-candidates.json) records positions found in the new raw main for each guard's full length and up to 32-byte/16-byte prefixes. All occurrences are retained when a prefix appears multiple times; the list is empty when none appears. Byte anchors do not prove function semantics, signatures, or control flow.

## Results

- Of 114 guards, **17** matched in full at exactly one location in the new original.
- **54** guards had at least one selected prefix found at exactly one location, including those 17.
- The rest did not yield a unique candidate by this method. Failed guards are not automatically removed and checks are not weakened.
- RAM bindings were not verified by this byte search. Whether old code's RAM constants have the same meaning in the new firmware requires separate tracing.
- A unique byte match in the new image is not guaranteed to be the correct function entry. These figures are not rebase completion, safety, or success rates.

## Checks required before an actual port

1. New locations, displaced instructions, branch targets, calling conventions, and surrounding control flow of 32 reviewed in-place patch sites.
2. Main functions and RAM constants in 18 source literal inventory files. Do not apply a single delta wholesale.
3. ABI and lifetime of allocator, zlib, display ownership, BLE ingress, message queue, input, sensor, microphone, brightness, and callbacks.
4. Consistency of 2.4 components and NOR/codec resources. Do not use 2.3 main unchanged or automatically downgrade other components.
5. New source audit and exact old-byte guards, generated output hashes, and malformed stream, lease expiry, allocation failure, and disconnect tests.
6. Verify that recovery boot, main, host, and web package select the same profile and reject other version combinations.

## Reproduction tool

Outside Git, `~/Library/Application Support/Blackwall/recovery/boot-2-4-analysis/audit-main-anchors.py` recreates the report from the input audit, old bundle, and new bundle. Originals and byte evidence were not committed to Git. The tool reads files and writes only candidate JSON; it has no transport import or image patch capability.

This research is preliminary material for the target implementation. Reproduction of existing Faceclaw/38 is not reported as completion of 2.4-based CFW.
