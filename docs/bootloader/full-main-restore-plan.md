# Virtual full-main restoration execution plan

2026-11-17 · bw-0564 · An execution unit for existing bootloader verification BV08/BV10. Denominator 12 remains. No physical-device, CFW-feature, or Astra authorization.

- [x] Add full-main opt-in permission verification preserving existing default scope. Permit only body 438010/3700064 bytes or vector 438000/16 bytes. Confirm Python RED (unimplemented function import)→GREEN 3 and six existing tests.
- [x] Pin original 2.4 main SHA and transfer full body through existing worker RAM-call snapshot→actual M55 recover.bin. Preserve the final 12 padding bytes from the virtual pre-modification MRAM snapshot. Do not write the vector yet on error/interruption.
- [x] Verify full MRAM before/after body and writer readback/response. Pass resulting MRAM as input to the next vector call and write vector last with the same original wrapper/writer. Verify full main SHA and all neighboring regions.
- [x] Put boot/main extracted from actual final MRAM on the frozen board and check natural handoff/main from boot reset. Check interrupted result's selection path from a fresh boot reset as well. The new runner does not relax the existing canonical SHA gate and separately enforces provenance from MRAM transfer result.

ROM writes in the full-transfer fixture are a functional model. This test transfers a worker RAM-call entry snapshot; it does not substitute for natural boot→UART2 authentication integration. If the full restore CRC utility was not actually executed, do not claim execution of the complete original host-install workflow. Full-stock/boot self-restoration is separate too.

Outputs are retained outside Git in private simulator as source, hashes, MRAM lineage, native logs, and owned journals. Native runs are sequential with host deadline 540 seconds/container 600 seconds, polling confirmed execution handles. After completion clean duplicate MRAM/SRAM/temporary dumps, preserving originals, reproducible inputs, and major evidence.

Final: [results](full-main-restore-results.md). Marker 0 failure retained; full ARM restore from cleared initial state → main/UI/frame succeeded; five interruption cases/fresh resets verified; independent 52-check audit and post-cleanup re-audit completed. Overall verification is 7/12; full-stock/auth/ROM remain incomplete.
