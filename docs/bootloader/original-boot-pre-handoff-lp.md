# MCU low-power transition before original handoff

Status: bw538 under verification. Original app selection passed, but handoff/main had not yet been reached.

Original PC 41ba1a writes 15 to MCUPERFREQ (40021000), changing request bits to 1. This RMW retains existing ACK/status bits and requests a transition from current HP to LP. The previous model accepted only request 2 (HP) and rejected it.

Pinned SDK permits LP 1 and HP 2, requiring active SIMOBUCK only for HP. LP writes the request and waits for ACK without waiting for HFRC2 ready. The model therefore expands to generate status/ACK for the requested target. Existing no-ACK/stuck-status profiles, HP buck/HFRC2-ready prerequisites, and blocking of unsupported/readonly bits remain. No claim is made about physical clock mux, frequency, or stabilization-time accuracy.

## Verification material

- `private:simulator/boot-mcu-lp-source-bw538-01/source-proof.json`: SDK lines 785–810/861–922 and original RMW.
- Same folder `model.patch`: only MCU request-target handling changed.
- `private:simulator/boot-mcu-lp-red-bw538-01/report.json`: previous model blocked original 15 request.
- `private:simulator/boot-mcu-lp-green-bw538-01/report.json`: 17 checks passed for LP response/failure profiles, HP readiness, readonly/invalid mode blocking, and more. This independent C# contract is distinct from natural ARM execution.

The existing low-request rejection fixture reflected the former unsupported LP scope. With positive LP verification, that negative was replaced by blocking unsupported request 0. Existing reports remain evidence of the model/scope at the time.

## Regression verifier metadata correction

All initial 11 conditions failed, but comparison with bw531's previous ten conditions and actual observations showed everything exact except new HFADJ metadata 25b800/read 0/write 0. The verifier's expected-bank list omitted this register added in bw532. The list was supplemented with the pinned DFP value and regression rerun in a new directory. Failure report and actual difference `legacy-diff.json` are retained; the previous run is not retroactively changed to green. No further model changes were made to fit expectations.

## Reaching original handoff→main

All 11 corrected regression conditions passed. At 71,979,738 original instructions/7.198 virtual seconds, boot manager → stock handoff 42dfe8 → main reset 5fbe3e each executed once in order. R0 at handoff/main was 438000 and final VTOR 438000. Code/system protection and CFSR/HFSR errors were 0; a new guard boundary appeared at main PC 495c96 writing MCUCTRL.VRCTRL 40020060=fe1ef. There is no display yet.

Authoritative records: `private:simulator/original-boot-pre-handoff-lp-native-bw538-01/frontier-proof.json` and `boot-phase-audit.json`. Selected normal profile's boot peripherals/unknown blocking and selection/handoff paths OB03/04 were completed. Main-entry MSP/CONTROL/VTOR simultaneous snapshot is still missing, so OB05 is not complete. Current progress is 4/8 (50%).

Twenty-two ELFs from two warm runs totaling 738480 bytes and an identical 149773-byte boot dump were cleaned up. Source, linker, model, logs, failure comparisons, hashes, and reproduction commands remain.
