# ADC internal timer restart by main after boot

bw-0543. Original main PC 0x57a78c's INTTRIGTIMER 0x40038040=0x8004001e is a normal restart setting only TIMEREN on stopped value 0x4001e. ADC was powered on/ADCEN 1/FIFO 0, but model TryStart supported only idle and stopped execution.

DFP Apollo510 ADC.INTTRIGTIMER is RW, and its CLKDIV description specifies TIMEREN DIS → configuration change → EN. The minimal change permits starting from initial idle or normal stopped. ADCEN/RPTEN/internal routing, previous TIMEREN 0, changing only enable bit, named divider/valid count, and integer source-clock checks remain. The same word while running does not restart it; other configurations remain rejected. Unsupported state after an event is not changed to stopped.

RED failed as expected at trigger-restart-0. GREEN passed 109 checks: 77 scan/FIFO and power regressions plus 32 timer checks. Four start/stop/restart cycles and rejection of active changes, previous TIMEREN 1, ADC disabled, zero count, and unsupported divider were checked. This is an isolated model test, not physical timing verification.

Original boot→main execution confirmed starts 2/events 4/ADC off requests 2/responses 4, timer stopped/FIFO 0. Bootloader and main each executed the ADC measurement path. With no unsupported guard, code protection, or system fault, budget ended at 100,068,225 instructions/10.0068225 virtual seconds. PC 0x4a2d10 is an original time-read helper; main/UI/frame completion remains outstanding. Screens 0 and 5/8=62.5% remain. Next extend observation time under the same model to check path progress.

ADC configuration fields retain current model storage; no claim is made that physical power-cycle reset/retention is identical. Keep this separate as a final-profile assumption and verify effects required by actual initialization requests at original source/boundaries. Virtual source Hz and constant ADC input assumptions remain as in the existing profile.

After confirming complete original boot/main byte identity, duplicate 3,849,841 bytes were cleaned up. Owned containers for two isolated and one native runs were confirmed removed; no ELFs. Key analysis, original hashes, commands, frozen model, and logs remain. See private simulator/adc-trigger-cycle-{source,red,green}-bw543-01 and original-boot-adc-trigger-cycle-native-bw543-01/frontier-proof.json/cleanup.json.
