# Shared ADC and GPU Power Registers

Status: analysis of shared bits, HAL structure, and the stock 2.4 table is complete. The executable model is verified separately. Full boot, display, actual power, and ADC calibration/conversion remain incomplete or unverified.

Six compile assertions compared ADC bit 13=`2000` and GPU bit 18=`40000` in public header registers DEVPWREN `40021004` and STATUS `40021008`. The HAL table and wait structure check power status using each domain's mask. The ADC entry in the previously verified stock 2.4 table at `6c8e40` also matches enable address/`2000`/status address/`2000`. The public enum is not assumed to be the ABI for the entire firmware. Source hashes and table evidence are preserved in private `adc-shared-power-research-01`.

## Model contract

`--adc-power-response active|stuck-off` is an explicit digital response hypothesis. It requires the existing GPU power model and ADCCAL storage. Shared reads combine the two bits' requests and states. Writes forward only the changed domain, preserving the other domain's state and GPU epoch. Writes changing unsupported bits or both domains at once are blocked without partial application. An unchanged write does not change domain state. The existing GPU-only path remains when the ADC option is not selected.

ADC enable requires ADCCAL bit 0=0. The original model's active buck prerequisite generalized an order observed in a main run. In bw526, the original boot was observed disabling automatic calibration and requesting only ADC while buck was off; the fixed HAL's peripheral enable also has no ADC buck prerequisite. The condition was therefore removed only from the two ADC paths; other devices' power gates remain. On the first STATUS read after a request, active responds with bit 13 and stuck-off responds with 0. This is a zero-delay hypothesis and does not verify actual rail, clock, readiness, or ADC conversion. If the automatic calibration bit turns on during a request, the model blocks without supplying a response. Turning off an already-on ADC or re-enabling it after cancellation is outside this stage; only cancellation while awaiting a response is supported. The calibrated flag remains 0. Existing blocks on GPU reactivation and the GPU engine also remain.

Domain-specific trace counts for the same register read do not represent different bus transactions. Existing DevicePowerReads/Writes count successfully handled bank accesses; rejected accesses are recorded by the strict guard. ADC records request, cancellation, and transition counts and does not count an unchanged bit as a request when the other domain is targeted.

## Small virtual tests

The 20 conditions in private `adc-shared-power-native-01/report.json` passed. The 17 new conditions cover ADC active/stuck-off with GPU on/off, request/readback, calibration gate, simultaneous change and other-bit blocking, unchanged writes, request cancellation, blocking off after ADC on, GPU off while preserving ADC, blocking re-enable of a retired GPU, partial/status writes, and the option not selected. Three existing GPU off policy and ADCCAL clear conditions also remained. These results verify the source-bit and explicit response hypothesis contract, not actual rail, ADC ready, clock, or timing.

## Five main runs and limitations

The three active inputs, stock 2.3, 2.4, and CFW, each transitioned the bit 13 request and response once, then were blocked writing `4001e` to ADC `40038040`. Compiling the public header confirmed correspondence to INTTRIGTIMER offset `40`. The ADC internal timer, conversion, and IRQ were not implemented. GPU remained powered off, request/status word 0, and epoch_retired=true; ADCCAL was 0. Stock 2.4 without the option was blocked at the previous PWRENADC `2000` request.

**Stuck-off stock 2.4 also reached the same ADC timer write.** ADC status was 0, the request bit remained set, and cancellation was 0. This observation proves neither safe failure handling nor actual power success. The fixed public HAL's adc_power_control WAKE also includes a call that does not check the periph_enable return. This is not generalized to an identical ABI in every binary or the result of physical failure. A subsequent ADC register model must establish power state and behavioral evidence. A failure profile does not automatically authorize output commands.

Private `adc-shared-power-verification-01/final-verification.json` compared the current C# source snapshot for native 20 and main 5. Missing CLI prerequisites were also rejected before file/Docker operations. Full boot, integrated display, and real-device verification remain incomplete.
