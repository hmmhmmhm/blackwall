# IOM cold power request during original boot

The owner was identified by comparing original shared request before 0/proposed 8/XOR 8 with IOM2 mask 8. This original request occurred before any buck start request or override. Based on pinned HAL peripheral enable and explicit digital power profiles, the buck-active condition was removed at one IOM dispatch. Other peripheral and GPU conditions remain; actual voltage/stabilization time and physical bus accuracy were not verified.

## Verification results

- `private:simulator/boot-iom-source-bw530-01/change-proof.json`: exactly one IOM dispatch changed.
- `private:simulator/boot-iom-cold-red-bw530-01/report.json`: reproduced existing cold-request block.
- `private:simulator/boot-iom-cold-green-bw530-01/report.json`: 30 basic cold checks across five IOMs passed.
- `private:simulator/boot-iom-cold-lifecycle-bw530-01/report.json`: 45 checks passed, including busy-off blocking and off/reactivation.

The existing `verify_iom_shared_bank.py` unready-rail rejection expectation was updated to check cold re-request and response. This task does not claim to have run that entire old CLI; the 45 checks run on the current full model/board support the new contract. The prior IOM2 rejection expectation in ADC cold tests was also replaced by the new IOM contract. Historical ADC 44/40-check reports remain evidence for the pinned models at those times.

## Original execution and next boundary

The corrected candidate executed 14,018,873 original instructions. It passed the IOM power-request boundary and strictly stopped at PC 41c5c8 writing CLKGEN.MISC (40004044)=fbbfc1. At actual termination IOM2/4/5/7 each had one request, two responses, and were powered off. This evidences original code turning each power on and off; IOM6 had zero requests/off. Code/system protection and CFSR/HFSR errors were 0; boot manager/handoff/main/frame were not reached. This write differs from previous HFRC bit 0-only control, so the allowed mask is not widened arbitrarily. Next compare original instructions with actual fields in pinned header/HAL. Authoritative record: `private:simulator/original-boot-iom-cold-native-bw530-01/frontier-proof.json`.

An identical 149773-byte boot dump was verified and removed. Owned Docker removal across four runs and original preservation were confirmed. No ELFs were generated; model, source, execution logs, hashes, and reproduction commands remain. Overall progress remains 2/8 (25%) before main integration.
