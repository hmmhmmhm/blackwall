# HCI advertising-stop boundary in sustained execution

bw502. Full 60 seconds had not yet succeeded. Source proof: private `sustained-hci-stop-source-01/report.json`.

## Actual original command

New integrated stock24 run stopped 56.988726 seconds post-screen at IOM6 `spi-peer-script-unavailable`. Guard address 0x40056120, value 0x501. Original PC0x582594 is SPI HAL command-register store, transfer length 5. Startup 59 commands/60 responses and five local-version queries were consumed; peer was WritePayloadReady.

Original 0x5823fc prologue pushes r3..r11/LR and subtracts 0x28 from SP. Saved R10=0x20067d7c, R8=5, R9=5, FP=0x2004abf8, LR=0x501829 were read. Comparison with original memcpy/transfer path in SPI writer 0x5017be shows source five bytes and transmitted copy at FP+0x40, 0x2004ac38, are both `010a200100`. Saved R9=5 is post-copy offset, not offset 0.

This decodes as H4 type 1, opcode 0x200a, parameter length 1, enable 0. Bluetooth Core 5.4 HCI 7.8.9 specifies LE advertising enable/disable with 0 disabled and 1 enabled. [Official HCI specification](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-54/out/en/host-controller-interface/host-controller-interface-functional-specification.html). Actual RF/controller timing was not verified.

## Model's incorrect premise and next verification

Hypothesis: all transmissions after startup can be treated as four-byte version queries. Actual original five-byte advertising-stop command disproves it. Current composer fixes localVersion kind from CS/header and CanBegin expects only four bytes, rejecting five. Do not solve by merely extending length/PC allowlists or ACKing all unsupported commands.

Next verify a small acceptance contract distinguishing supported command headers/opcodes/lengths/arguments while retaining existing SPI/GPIO/CS, command/response completion, caps, and reset rules. First distinguish observed version query from advertising stop, then compare advertising state and subsequent original calls/specification. Startup five advertising commands and existing reconnect/post-reset models are reusable material. Existing model support for a specific post-disconnect sequence is not expanded to post-natural-initialization advertising stop.

Existing `runtime_reconnect_model.py` uses fixed params/enable order after disconnect/reconnect workflow; `post_reset_advertising_model.py` uses data-first order of next controller generation. Neither is the current post-startup runtime events 0/generation 0 boundary. Do not modify original buffer or CPU branches/tasks to create those prerequisites.

Original stopped; container absence and worker termination confirmed. Final matrix preserved as completed0/12 and failed, not restarted. New acceptance contract was not yet implemented/verified. Overall Goal active 6/10; physical device/Astra/external publication 0.

## Selected command profile verification and rerun

bw503 `startup_hci_commands_model.py` optionally composes into existing startup-version component. Default advertising-stop budget 0 remains; only explicit 1 adds observed `010a200100`. Supported candidates check prefix, transfer chunk length, opcode, and full arguments together to distinguish four-byte version from five-byte advertising stop; other opcodes, enable 1, and reserved values unsupported. Existing CS/GPIO/command completion, response wait/consumption, cap, and reset checks remain. New connection-event injection after advertising stop is also rejected. This is not RF or EM9305 firmware execution.

Existing model device red failed at `captured-payload-supported-5-0`. New device tests passed normal 60, two-byte chunks 66, existing selected-profile regression 60, version-budget-exhaustion 120 = 610 checks. Includes 32-bit SPI word check, incomplete response-header retry, write during response/short and long receive rejection, bad configuration, budget/reset. This is not original ARM execution. Private `startup-hci-commands-verification-01/report.json` pins original source and compiled model.

Runner selects this compound component and board budget 1 only when `--startup-command-profile version-and-advertising-stop` explicitly specified. Before/after component, unit-test SHA, and command profile are recorded in existing controller declaration and identically reconstructed by independent saved audit. Original runtime/buffers/branches/TCB unchanged.

New original 60-second capture is `sustained-hci-stop-native-01/stock24`, 794 source files in `sustained-hci-stop-bw503-01/source/tools`. Actual owner/container running confirmed and worker connected. Only if first run succeeded would remaining 11 proceed sequentially; stop at first failure. Prior failure folders/state preserved. Passing new original's 57-second boundary/full 60-second success was still under verification. Earlier unimplemented wording was pre-implementation history.

## Advertising parameters follow-up and state procedure

bw503 original confirmed advertising stop 1/response consumed 1 and version 6/6, but stopped immediately at 19-byte command at 56.989024 seconds. Original saved R10/R8/R4 and copied buffer matched `0106200f400640060001000000000000000700` and first nine-byte chunk. Pinned in private `sustained-hci-parameters-source-01/report.json`. This failure is not counted as full 60-second success; worker stopped at completed0/12.

bw504 optional procedure is advertising stop → exact parameters above → advertising-enable command `010a200101` from existing startup/reconnect. Stage advances only after corresponding response consumed; version queries can interleave. Connection rejected before advertising resumes, and even if version budget exhausts first, ongoing advertising procedure may finish its specified three stages. Unsupported commands/arguments/order are not ACKed. Existing two-command model without params profile preserved. Resume command is supported behavior reusing already verified existing-profile material, not claimed actually transmitted in this failed capture.

Device tests passed normal 136, two-byte chunks 164, existing selected-profile regression 60, version-budget exhaustion 120 = 480 checks. Not actual original ARM execution; inputs and compiled model pinned in private `startup-advertising-procedure-verification-01/report.json`. Existing-model 19-byte rejection red is `captured-payload-supported-19-0`.

New `--startup-command-profile version-and-advertising-reconfigure` records optional compound component, budget 1, exact paramsHex, and device-test SHA in plan. Audit checks component/board differences and disable/params/enable counters and phase/state. Unobserved params of other firmware are not automatically allowed.

New capture at that time: `sustained-advertising-procedure-native-01/stock24`, pinned source 796 and worker in `sustained-advertising-procedure-bw504-01`. Actual owner/container/worker alive confirmed. Only after first 60-second success would remaining 11 proceed sequentially; stop on failure. Earlier failure folders/states preserved. New original procedure consumption/60-second success was still under verification.

## Host first-render observation limit

First procedure original terminated before sustained observation. At render-return host 30 seconds it had advanced only virtual 148.243 ms; same return in previous normal run was 234.091/234.129 ms. Guard/fault/runtimeError 0, six initial SRAM pins identical, screen-complete 0. Actual run/worker ended and container absence confirmed. It was not a live run restarted after mistaking tool observation timeout for termination.

bw505 retains original virtual one-second limit, watchdog, MIPS, branches, and timers, selecting only first-render host limit 300 seconds. Exactly one literal each changes: stock24 render-return 30 seconds and old2-family detail-frame 120 seconds. Plan records original runtime baseline SHA, change type, and new 300-second limit; observation insertion is independently checked against baseline. It does not assume first screen occurred or force successful return. Fourteen control/rejection units and one substitution per original confirmed.

New capture at that time: `sustained-render-guard-native-01/stock24`; pinned source 796/worker in `sustained-render-guard-bw505-01`. First screen, original procedure, and 60-second success were still being verified. Earlier running-language remains historical.
