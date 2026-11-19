# Focused boot observation and continuous execution

BW536 retained model, board, and original, removing only two detailed delay entry/return PC observations. Important reset/CRT/FPU/C-init/data-init/boot-main/board-init/manager/handoff/main-reset points remain.

## Control under the same 4.2-second profile

Previous bw535 and new focused runs had exactly the same 1110 UART bytes, NOR state, and boot globals, with matching order/hit counts at major stages. Code/system protection, strict guards, and CFSR/HFSR errors were 0. End PC/registers were not identical. The new run progressed to 4.2081362 seconds, 8.1073 ms longer than 4.2000289 seconds previously; the instruction-count difference of 81073 exactly corresponds to that extra time at 10 MIPS. Do not ignore this difference and claim complete execution equivalence or observer neutrality.

Authoritative record: `private:simulator/original-boot-focused-native-bw536-01/semantic-pair-proof.json`. Follow-up observes original manager→handoff→main→completed frame with the same focused observation under virtual 10-second/host 300-second limits. If a completed screen appears, stop and copy it using the existing GPU frame counter. Do not inject a frame or change CPU path. Judge actual completion only after comparing stages, guards, and frame contents.

Post-stop stack collection was limited to at most 2048 bytes within mapped SRAM so main task stacks can also be read safely. If SP is outside range, record a diagnostic error only; do not alter the original or supply a fake stack.

## Subsequent continuous execution

At 51,785,412 original instructions/5.1786 virtual seconds, boot manager 42e650 was entered once. UART logged creation of /firmware, /ota, /user, /log, littlefs boot_count 1, Even Bootloader start, and DFU task sync start/end in order. Code/system protection and CFSR/HFSR errors were 0. The next boundary is original 42e582 reading MRAM metadata at 7fe000. guard_mram_tail blocked it; raw main or full memory guard is not relaxed. Handoff/main/frame were not reached.

Authoritative record: `private:simulator/original-boot-focused-ten-second-native-bw536-01/frontier-proof.json`. Identical boot dumps from two runs totaling 299546 bytes were verified and cleaned up, and owned Docker removal confirmed. Actual UART, stack, model, logs, SHAs, and commands remain. Next investigate original update-flag function and upstream recovery MRAM metadata format/default state. Do not assume unverified physical state is a normal stock value.
