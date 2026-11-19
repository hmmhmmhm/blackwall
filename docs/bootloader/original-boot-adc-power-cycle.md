# ADC power cycle from boot to main

bw-0542. Original main PC 0x494d78's write 0x40021004=0x2000 had before 0/XOR 0x2000: a restart request for ADC already used and turned off in boot. Existing BlackwallAdcPower was a one-epoch model allowing enable only at initial off.

Public HAL ADC request/status tables and periph_enable request OR/status wait and periph_disable clear/status wait were compared. There was no basis for assuming permanent retirement across a digital power cycle. A new request is accepted and retired cleared only when powered off, explicit off response succeeded, request/status 0, auto-calibration disabled, and quiescent. Response occurs on a separate status read per existing profile. Host does not force power registers or guest PC. This does not claim complete reproduction of ADC power-on reset or analog state.

Seventy-seven isolated checks passed, including existing 39 scan FIFO conditions. Restart request failed before the change; afterward tests checked three repetitions, rejection of restart when not ready, not quiescent, pending off, stuck on/off, or cancelled, and rejection of early response. The existing test rejecting re-enable of a retired epoch was updated only for successful powered-off state. Current inspect confirmed test execution image tag matches pinned SHA e840c2b9….

Original boot→main native passed restart at 72,069,744 instructions/7.207 virtual seconds with ADC requests 2/responses 3/on/status 0x2000/retired=false. Next is internal trigger restart write 0x40038040=0x8004001e at PC 0x57a78c. Before: trigger 0x4001e, timer stopped, starts 1/events 2, FIFO 0, ADCEN=true. Existing timer accepts start only from idle. Code/system faults 0, screens 0. This is not completed main/UI boot. Overall 5/8=62.5% remains.

After execution, complete guest boot/main bytes matched canonical; duplicate dumps totaling 3,849,841 bytes were cleaned up. Owned containers for two tests and one native run were confirmed removed. No ELFs/compile outputs were generated. Original, source, manifest, commands, logs, and analysis remain.

Evidence: private simulator/adc-power-cycle-source-bw542-01/source-proof.json, adc-power-cycle-{red,green}-bw542-01, original-boot-adc-power-cycle-native-bw542-01/frontier-proof.json and cleanup.json.
