# Main waiting for HUD input after original boot

bw-0545. Model, board, and original input were retained; peer, GPIO, and SRAM were read only after the 20-second execution stopped. No additional PC hooks or external input were used. CPU registers/instruction count matched before and after all post-stop observations, and the machine was confirmed paused.

Original SRAM's doubly linked lists, TCB owner/self pointers, ranges, and saved stacks were verified with existing linked_graph/display_waits. Current task among 29 active tasks is IDLE. ui_task and displaydrv_mgr_task are each in queue receive with item 12/36 bytes, capacity 96, messages 0, receiver 1; ambiqdraw waits on a notification counter. Thus frame 0 is not interpreted as main stuck in initialization. OB06 among the current eight conditions requires a completed frame and remains incomplete.

IMU FIFO ready, explicit functional GAF services 2/calculation 0/phase disabled, UART0 on/TX 13/RX 0, GPIO27 high/pad 0x53/IRQ enabled, touch events consumed 0, and GPU powered-off/captures 0 were confirmed. This does not verify actual sensor fusion, BLE RF, or device version. Current virtual input has not yet supplied touch/UART responses beyond the boot/main path.

The existing first-screen profile is virtual GPIO27 pulse → original touch handling → two UART0 requests and ACKs → display request/response → original UI/render. Next use this verified external-device input on the same booted board. Do not directly modify guest PC/TCB/queue/readiness flags/memory. Generate virtual peer responses only after checking actual transmitted requests and IDs, retaining pre/post-input and rejection boundaries.

After confirming complete boot/main byte identity, duplicate 3,849,841 bytes were cleaned up. Full SRAM 3,670,016 bytes supporting the original task graph is retained as analysis evidence, not reproducible-build cache. Owned container removal confirmed. Source/manifest/commands/logs remain. Overall 5/8=62.5% remains.

Private simulator/original-boot-main-input-state-native-bw545-01/readiness-proof.json, kernel-state-proof.json, exports/main-input-state.json, and cleanup.json. The existing tools/inspect_imu_ui_dependency.py linked-list/wait-stack checker was reused for read-only analysis; diagnostic caller insertion was not executed.
