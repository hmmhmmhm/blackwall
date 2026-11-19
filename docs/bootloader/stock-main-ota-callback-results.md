# Stock OTA callback and readback verifier

2026-11-17 · bw-0570. **A 4 KB write by the upper original main callback and normal OTA readback-verifier return were confirmed.** Write-error/corruption cases reached mismatch at the original comparison, but final verifier return is unconfirmed because the following error log's RTC dependency is unsupported. BV11 is partial, overall 7/12=58.3%. This is not natural BLE OTA, full boot restoration, or physical recovery success.

## Cause of the previous boundary and connection

The earlier minimal fixture's 40021000 read was original `495e88` delay helper querying MCU clock mode. Existing `BlackwallMcuClock` and `BlackwallHalStorage` were reused unchanged to provide explicit HP22 profile; only mode read is used here. This does not imply physical 250 MHz or per-instruction cycle accuracy.

From 32 bytes actually observed natively in [existing GAF delay analysis](../hardware/sensors-input/gaf-delay-clock-contract.md), six called bytes `0138fdd17047` were confirmed. They also match original main literal 7bf54f and form the original `subs/bne/bx` ARM loop. These six bytes were loaded at diagnostic ITCM 40. **The complete original boot ITCM initialization stream was not executed by this caller.** This isolated function profile reuses six code bytes from a previously initialized state. Observation-file SHA is a9792dcd…; manifests retain the full hash. Other ITCM regions are not permitted by execution/read guards.

Delay profile must be explicitly selected together with chip profile. Default minimal fixture and historical frozen results remain. FPU/CPACR=f00000 is an initial condition of initialized-main diagnostic environment; CONTROL/FPCA, cached MRAM capacity, and callback pointer are not forced. The actual original getter calculated 4 MiB capacity and stored it in original SRAM cache.

First native attempt failed before guest execution because registering `MappedMemory` at address 40 violated Renode guest page 400 alignment. Only mapping was corrected to 0..400; permitted execution/read remains 40..46. Failed source/log/manifest remain.

## Callback results

A synthetic SRAM caller invoked original `5c69f8 → 5c6994 → 488d34 → 4f5864 → ROM`. It used the same 434000..435000/4096 bytes and virtual pre-modification snapshot payload as before. Original IRQ/power and nonzero callback execute unchanged. Only ROM program is the existing fixed ABI/range functional model.

| Condition | Callback normal return | Write | Subsequent original memcmp |
| --- | --- | --- | --- |
| Normal | 0 | 4096 bytes | 0, match |
| ROM status 7 | **0** | 0 bytes | ffffffff, mismatch |
| First-bit readback corruption | 0 | 4096 bytes then one-bit corruption | 1, mismatch |

All three confirmed ten ITCM delay calls/returns, ten mode reads, device-info 4 MiB, and fault/guard 0. Original power enable/disable each once, nonzero callback twice, ROM once, ROM-entry PRIMASK 1 and normal-return PRIMASK 0. CONTROL is 4 after original float instructions. Full 4 MiB was compared; outside the allowed page remained unchanged.

Like the buffer, callback swallows ROM errors. This confirms at the upper layer that API 0 alone cannot determine restoration success.

## Original OTA readback path

Separate `--verification ota` calls **original 446ab4** instead of synthetic memcmp, with destination, expected payload, length 4096, and existing SRAM 20000394 ops table. Original ops table read callback is 5c69d1. Path: `446ab4 → 480c14(cache helper) → 5c69d0 → 5c6994 → 439be4(memcpy) → 480dc8(memcmp)`. Original instructions and logging configuration were unchanged.

- Normal: write callback 0 and verifier 0 returned normally. Two getters (write/read), one read callback, and one original comparison were confirmed.
- ROM status 7: actual read callback read existing MRAM page, and original comparison returned 1, detecting mismatch.
- First-bit readback corruption: original comparison of the actual read page returned ffffffff, detecting mismatch.

Comparison argument order is opposite the earlier synthetic memcmp, so mismatch signs are also opposite. Equality is determined by zero. Both final error runs observed the value at 446b0e immediately after comparison and saved all 4096 bytes of actual OTA read buffer 203214a0, confirming exact match with final MRAM page.

**Complete error handling remains incomplete.** After comparison, the original logging path required RTC/CLKGEN.OCTRL 4000400c and stopped unsupported. CFSR/HFSR 0, model violations 3, PRIMASK 1 at stop. This is not normal return or IRQ restoration. API/comparison general registers in incomplete reports are intermediate state, not return values. Memory observation/stop is not a pre-access veto; effects after unsupported reads are not interpreted as hardware results. The previous ROM-error run without observer was also retained at the same boundary.

Isolated CPU SCB.CCR retained reset 0. Original cache helper actually reads CCR and executes DSB/ISB path. CCR was not forced off as a bypass, but natural main's existing cache-enabled context or physical cache maintenance was not verified.

## Audit and cleanup

Outside Git, `simulator/stock-main-callback-bw570-01` preserves platform registration failure, `-02` three callbacks, `stock-main-ota-verify-bw570-01` normal/initial errors, and `-02` two errors observing comparison/actual readback. Of seven guest executions, four returned normally and three reached unsupported RTC logging boundary. There was one additional registration failure without guest execution.

`stock-main-callback-audit-bw570-01..03` audited actual source/hashes, original inputs, ITCM literal/observation, full MRAM, callback/IRQ, original comparison, actual read buffer, and unsupported classification. Before cleanup 162 conditions; after cleanup saved audit-source and frozen support modules ran in `/tmp` and passed 169. **Audit pass includes accurate classification of expected unsupported records and does not mean those runs succeeded.** The previous ten-run 181-condition audit also still passed. Four input/original-delay protection units confirmed RED→GREEN.

Termination and container absence for eight owned native journals were confirmed. Seven full dumps and eight reproducible ELFs were checked and cleaned up, reclaiming 29,888,992 bytes. Each final 4 MiB/hash can be reconstructed from final 4 KB page and canonical initial MRAM. Original/observations, manifest, source, assembly, caller binary, native logs, actual OTA readback, raw reports, and audits remain. Private firmware is not added to Git.

## Reproduction and next checks

Existing pinned private inputs, pinned Renode image, and LLVM 21 are required. Use new output names.

```sh
bw_assets="$HOME/Library/Application Support/Blackwall"
python3 -B tools/run_stock_main_mram_probe.py "$bw_assets/simulator/callback-new-01" --entry callback --fault success --chip-profile --delay-profile
python3 -B tools/run_stock_main_mram_probe.py "$bw_assets/simulator/ota-verify-new-01" --entry callback --fault success --chip-profile --delay-profile --verification ota
python3 -B "$bw_assets/simulator/stock-main-callback-audit-bw570-03/audit-source.py" "$bw_assets/simulator/callback-audit-new-01"
```

Next sequentially restore the **entire synthetic virtual-original boot footprint of 159744 bytes** with this original main callback, verify using original verifier, and check whether actual result MRAM can connect to a new original boot reset. Current single-4-KB success is not counted as full stock. Distinguish the already confirmed resident boot self-overwrite path. Gaps in natural UART authentication/recovery, original ROM, factory INFO1, and version combinations, plus separate physical authorization boundary, remain.
