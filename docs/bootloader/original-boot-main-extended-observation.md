# Extended observation of original main

bw-0544. After bw543's ten-second budget ended, only the virtual budget was extended to 20 seconds with the same model/board/initial input. Host 300-second/container 420-second limits remained. Actual code, initial RAM, peripheral state, and start PC were unchanged.

Budget ended at 139,370,233 instructions/20.178 virtual seconds at PC 0x44e176. Unsupported guards, code protection, and CPU/system faults were 0. Original 0x44e174 is WFI and 0x44e176 ISB. Total time includes sleep and therefore is not instruction count ÷ 10 MIPS. BLE initialization UART logs added EM9305 init status 0, BLE FW Ver 1.2.3.4, and INFO nine times. Version is an explicit virtual-peer response, not a physical BLE version read.

Display captures 0/bytes 0; OB06 remains incomplete. This result alone does not establish that every app task is ready or stable boot is complete. Since the main sleep path was reached beyond a simple delay, the next step is read-only observation of device/RTOS/external-input readiness.

Comparison with the existing stock24 first-screen runner shows it originally opened UI after main initialization using virtual GPIO27 touch and UART0 peer ACK/display reply. The current original-boot runner has not yet supplied those inputs. Verify whether that state explains frame 0, then use verified wire inputs on the same virtual board. Do not substitute a path forcing original UI/TCB/branches.

After confirming full original boot/main byte identity, duplicate 3,849,841 bytes were cleaned up and owned container removal confirmed. Model/board exactness, input SHAs, commands, logs, and key analysis remain. Private simulator/original-boot-main-extended-native-bw544-01/frontier-proof.json and cleanup.json. Overall 5/8=62.5% remains.
