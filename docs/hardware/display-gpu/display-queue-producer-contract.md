# Original display queue36 producer and driver-delivery conditions

Work bw-0340 used saved SRAM from three originals in [current sensor/UI wait audit](../sensors-input/imu-startup-ui-dependency-audit.md). Without new Renode main execution or hardware access, original ARM function send/receive contracts and limited consumer paths were verified.

## Message path confirmed

| Item | Stock 2.4 | Stock 2.3 / Faceclaw 38 |
| --- | --- | --- |
| Type 3 producer | `0x47ee8e` | `0x47ac1e` |
| Context base / queue offset | `0x200023f8` / `+0xc` | `0x20000754` / `+0xc` |
| Actual queue | `0x20074e60` | `0x200758b8` |
| Consumer after queue get | `0x47e9e8` | `0x47a780` |
| Mode slot / saved value | `0x20076f88` / 0 | `0x20077818` / 0 |
| Driver wrapper | `0x4ee7e2` | `0x4e4112` |
| Original ROM vtable | `0x71097c` | `0x72bd7c` |
| Vtable `+0x28` callback | `0x5bbd22` | `0x5b279e` |

Addresses are for pinned images verified here and are not reused on other versions. Task saved exception frames, actual queue-get return addresses, wrapper prologue, live saved r6/r7, and context TCB/queue were cross-checked. Arbitrary stack words or raw address matches alone do not establish connection.

Producer takes six 32-bit arguments: r0–r3 and two caller-stack words. It clears 36 bytes using original memset, then creates nine words:

`[3, arg0, arg1, arg2, arg3, arg4, arg5, 0, 0]`

Queue put arguments are handle, message pointer, priority 0, timeout 1000. Queue begins capacity 96 / item 36 / messages 0 / receiver 1. This function copies six words by value. Even pointer-like values are not dereferenced as byte payload or copied to a separate ring. Business meanings and later callback memory ownership remain undetermined. `[0,0,0,0,576,288]` is a representative isolated-test input, not evidence that actual main generated/scheduled it.

## Execution results and isolation boundary

Representative input, asymmetric values, and high-bit/address-like values were tested per image: three images × three inputs = nine combinations.

1. Full producer and original queue/kernel internal calls executed. Return 0, messages 0→1, receiver 1→0, display TCB event container→0, write pointer +36, and exact 36-byte storage confirmed.
2. Original queue get received same 36 bytes, returned 0, and messages 1→0. RTOS wait-list changes are original function results. PendSV and actual display-task resumption were not executed.
3. Consumer ran from **immediately after** queue-get with synthetic stack/message. Three preparation helpers and one eligibility function were explicitly stubbed. Conditional branches checked for four combinations eligibility 0/1 × mode 0/1. This does not verify natural main execution or actual preparation-helper effects.
4. Eligibility 0 and last message word 0 suppress processing. Even with eligibility 1, mode other than 1 skips type 3 driver call. In a diagnostic permitting both, original six arguments reach driver wrapper. **Actual saved mode was 0 in all three images.**
5. Driver wrapper was separately followed from actual RAM slot → ROM vtable → callback. Execution stopped **immediately before** callback's first instruction; six arguments were preserved. Callback execution, DMA transfer, framebuffer, and pixels were not confirmed.

Per combination: two producer observation on/off runs + one get + four consumer + one driver wrapper = eight, total 72 isolated original ARM scenarios. Engine is Unicorn 2.1.4 Cortex-M7, distinct from Renode Cortex-M55 reset→main execution. Each fixture uses SCS 0 and synthetic call ABI/stack. Timeout and physical power state are not verified.

Producer code-observer on/off final full SRAM, WORK, SCS, general registers/SP/LR/PC/xPSR matched. No original memset write hook used. This is final-state equivalence for tested inputs, not physical timing or full task-scheduling equivalence.

## Verification material

- Tool: `tools/probe_display_queue_producer.py`.
- Private `simulator/display-queue-producer-05/{probe.py,report.json}` and `display-queue-producer-frozen-02/`.
- Private `simulator/display-queue-verification-02/manifest.json` and `verify-display-queue-02.py`.
- Inputs: bw338 capture/audit manifest and bw339 task-map manifest hash-checked. Frozen rerun also had 72 cases; two artifacts byte-identical.
- Nine negative controls mutating message type, mode guard, and queue binding for each of three images were rejected. Eleven existing peripheral-model hashes match.

Diagnostic history preserved. `display-queue-producer-01` failed by comparing caller registers pushed by wrapper against live registers. `02/03` failed due to instruction-offset verification errors in new inspector and were corrected. `04` passed; `05` added task-map manifest pin. First verification failed by incorrectly comparing key formats of full C# list and existing 11-file list. `verification-02` compared actual hashes of same 11 files. These are not interpreted as firmware/model behavior failures.

## Next unit

Trace actual producer and preparation helpers of initialization path where type 1 consumer writes mode 1. Do not inject type 3 or force mode to claim main-screen success. D3 completion requires legitimate UI initialization input → display activation → original render calls → framebuffer. Unknown defaults of sensor ROM 153 bytes are not arbitrarily expanded as zeros.

Overall completion conditions remain 13/29=44.8%, scope v2. Full boot, app loop, integrated UI, and physical installation/recovery remain incomplete.
