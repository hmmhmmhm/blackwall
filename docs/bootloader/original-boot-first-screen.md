# From original bootloader to stock main and display

The subsequent bw550 [final audit of all eight conditions](original-boot-completion-audit.md) is complete. Progress and remaining work below reflect the state at this task.

bw-0547. On one virtual board, stock 2.4.0.24 boot reset (0x410000/0x432cb3) → original handoff → stock main reset (0x438000/0x5fbe3f) → virtual GPIO27 touch → original UART transmission/peer response → original UI/app 1 callback → renderer → completed 576×288 display were connected. This is not execution from Boot ROM or physical display success.

## Directly inspected results

Final 02 stopped at the first nonuniform frame among three completed captures. A8 is 165,888 bytes with 5,545 nonzero pixels and seven levels valued 0..7, byte-identical to the corresponding buffer in exported original guest SRAM. Raw SHA256 is `81200ab102c507de6a5853a33086958d16bcb93168ff631ee76b6c8c391adba2`. PC 0x560f6a is bx lr after original GPU writer's str r1,[r0] at 0x560f68. Read-only observation stopped after completion before reuse, without forcing a branch.

Raw A8 was losslessly converted to grayscale PNG and directly inspected. The raw preview is dark because initial fade values are low. A separate diagnostic contrast enlargement (0..7→0..255) also showed clock/day/status and “No news available”, “Add new sources in the app” in the right border panel. Raw data was unchanged and enlarged brightness is not presented as physical brightness.

Total was 203,695,431 instructions/20.696792 virtual seconds; CFSR/HFSR, code/system protection, collected unsupported guards, and GPU rejections/errors were 0. Time includes main's wait for external input and explicit functional cadence. It is not interpreted as physical boot time, device performance, or long-term stability.

## Execution state and functional profile

Execution used 10 MIPS through original UI dispatch 0x4456e8, applying the existing hal-loop-equivalent-v1's 167 MIPS only in actual HP mode 22. The observer briefly paused the machine without changing PC/TCB/returns/branches/readiness flags. R0–15, instruction count, virtual time, and complete 3,670,016-byte SRAM matched before/after transition. Its own checkpoint deadline was canceled before resumption.

Virtual GPIO/UART responses were correlated with CRC, length, and ID of frames actually transmitted by the original. Guest executed RTOS/UI/renderer itself. Functional model, constant ADC, public GAF defaults, reference GPU sampling/packing, and external-peer assumptions remain. Sensor-ROM mathematics and every GPU ISA/physical timing were not completed.

Initial 01 continued for 500 ms, generated six captures, and its raw preview UI was directly inspected. However the frame source buffer was reused by the next update, so final-RAM equality failed. That failure was retained; 02 added original GPU post-store observation to prove same-time RAM exactness. The late RAM mismatch in 01 was not changed to success.

After execution, original boot 149,773 bytes/main 3,700,068 bytes matched canonical in full. Duplicate images and cadence-comparison RAM from two captures, 11,189,873 bytes each, totaling 22,379,746 bytes, were cleaned up. Final guest RAM, raw frame, and PNG remain as direct verification evidence. Two owned containers confirmed removed. Missing PIL was handled without installation using a standard zlib/struct lossless PNG writer.

## Remaining acceptance criteria

OB06 complete. Overall 6/8=75%. Two reproductions of the same final cold profile and corruption/unsupported-input rejection (OB07), and pinned manifest/reproduction CLI/independent audit/final cleanup (OB08), remained incomplete. Obtaining a screen alone does not complete the full goal.

Private simulator/original-boot-ui-cadence-native-bw547-02/screen-proof.json, exports/complete-screen.bin, exports/complete-screen.png, exports/contrast-preview.png, and cleanup.json. 01/framebuffer-reuse-proof.json retains the failure. tools/renode-complete-screen-observer.cs is optional read-only observation and does not change the existing hardware model.
