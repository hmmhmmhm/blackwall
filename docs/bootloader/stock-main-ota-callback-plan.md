# Stock OTA callback dependencies and error-propagation verification

2026-11-17 · bw-0570. Connect existing adapter/buffer unit evidence to the upper original callback. BV11 remains partial and overall 7 of 12.

- Compare existing BlackwallMcuClock HP22 read contract and actual observed six-byte ITCM delay against original main literal. Reject code mismatch and missed observations. Do not present this as execution of the full initialization stream.
- Supply initialized ITCM/clock only through a separate opt-in profile. Do not bypass original capacity getter, alignment/IRQ/power, callback, or write/compare. Preserve the default minimal profile and historical frozen runs.
- Check actual MRAM, return, existing callback preservation, fault/guard, and IRQ restoration for callback normal/ROM-error/readback-error cases. Where needed, connect the actual OTA verifier as original code and distinguish it from synthetic memcmp.
- Preserve unsupported boundaries and initial harness failures separately. After full-MRAM comparison and independent audit, clean duplicate dumps/builds. This does not substitute for natural BLE OTA, full stock, or physical certification.

Initial RED confirmed unimplemented `validate_delay_bytes` ImportError before implementation. First native failed before guest execution because MappedMemory registration address 40 did not meet guest page 400 alignment. Mapping was corrected to 0..400 while guard permits execution/read of only the actual six bytes.

Results: [normal return, error discrepancy, RTC boundary, independent audit and cleanup](stock-main-ota-callback-results.md). Original OTA error final return and full stock remain incomplete.
