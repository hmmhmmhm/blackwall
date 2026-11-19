# Original UI queue producer and separate payload contract

Work bw-0269. The original send function connected to the 96×12-byte UI queue identified in [display task wait conditions](../../firmware/main-display-integration-frontier.md) was found. Function contracts were checked with verified full SRAM and pinned original ARM without newly booting full original main. No physical-device access.

## Confirmed send/receive path

| Original function/state | Stock 2.4 | Stock 2.3 / Faceclaw 38 |
| --- | --- | --- |
| Type 7 producer | `0x446230` | `0x4461cc` |
| UI queue handle slot | `0x20076f74` | `0x20077810` |
| Actual UI queue | `0x20074e10` | `0x20075868` |
| Queue put wrapper | `0x443210` | `0x443298` |
| Queue get wrapper | `0x44328e` | `0x443316` |
| Payload ring object | `0x200762bc` | `0x20076c74` |
| Ring writer | `0x476654` | See source contract in private report below |
| Ring reader | `0x47673c` | See source contract in private report below |
| Type 7 consumer parser call | `0x445c3a` | `0x445be6` |
| Payload parser | `0x444834` | `0x44480a` |

Producer takes three arguments and makes a ten-byte little-endian payload `u16(first & 0xffff), u32(second), u32(third)`. It executes actual original mutex take → ring write → mutex release, then calls queue put. Immediately before queue send, arguments are queue handle, message pointer, priority 0, timeout 1000.

The 12-byte queue message consists of three 32-bit words `[7, 0, 10]`. First byte of first word is type, argument at offset 4 is 0 in this function, and offset 8 is payload length 10. Ten-byte payload is in a separate ring, not the queue. Do not generalize that all UI types share this payload structure or meaning. Timeout is an original API argument; actual elapsed time and timeout path were not tested.

For example inputs `0x1234, 0x89abcdef, 0x76543210` produce payload `34 12 ef cd ab 89 10 32 54 76` and queue message `07 00 00 00 00 00 00 00 0a 00 00 00`. Upper 16 bits of first argument are discarded. Business meaning and ranges of the three fields remain undetermined.

## Original code execution results

Zero input, asymmetric pattern, and high-bit/truncation pattern were supplied to each of stock 2.4, 2.3, Faceclaw: three images × three inputs = nine combinations, each starting from the same initial RAM.

1. Full original producer including internal calls returns 0. Queue messages 0→1, receiver waiters 1→0, actual UI TCB event-list container becomes 0. Queue write pointer advances 12 bytes and actual queue bytes match expected message.
2. Original queue get returns 0, receives same 12 bytes, messages 1→0.
3. Original ring reader returns 10, reads same payload, and read/write cursors both become 10. Ring capacity `0xa000`.
4. Original consumer parser prefix restores ten bytes to original `u16/u32/u32` values. It stops just before first context getter call, so subsequent business behavior does not execute.

Total 27 function API transactions (producer/queue get/ring reader) and nine parser prefixes. For all nine combinations, a read observation immediately before producer queue send was compared to hook-free execution; final full SRAM/WORK/SCS/general registers matched. Instruction count of observed runs per producer was 861. This does not mean full PC paths of hook-free runs were collected. No memory-write hook was used.

## Scope and limits

Engine is Unicorn 2.1.4 Cortex-M7 executing original ARM code itself. Explicit function arguments, work stack, and return boundaries were provided; SCS at each function start is separate zero memory. Only SRAM was passed between functions. This is not native integration of actual M55 interrupts, PendSV, and task context switching. Host did not alter kernel RAM in place of code or skip internal functions/branches/returns.

Evidence that original queue code releases UI event wait differs from evidence that actual UI task is rescheduled and runs its business handler. The latter is absent. Type 7 is an original UI control path, not confirmed as HUD redraw command. After parser, code performs context lookup, command-specific branches, and UI state changes. Do not arbitrarily inject type 7 or force consumer wake to create a screen.

Other producer candidates in the same area include types 2, 3, and 5. Full function execution or meanings remain unconfirmed, so they are not labeled render commands. Causal relationship of actual screen-update producer and callers requires further analysis.

## Preservation and reproduction

`tools/probe_ui_queue_producer.py` checks unique original signatures, literal queue slots, source prologue, ring-cursor instructions, and type 7 consumer branch, and rechecks full RAM export and main hash. Functions are not established solely by relative distance between adjacent API addresses.

Outside Git at `~/Library/Application Support/Blackwall/simulator/`:

- `ui-queue-producer-01`: first inspector and failure record. It checked writer's 32-bit `pop.w` at an incorrect 16-bit boundary. Only source inspector was corrected; original unchanged.
- `ui-queue-producer-02`: first passing producer/queue/ring results.
- `ui-queue-producer-03`: final analysis adding consumer-parser source connection and prefix execution.
- `ui-queue-producer-verification-01`: pinned inspector and 15 local dependencies, hash manifest.
- `ui-queue-producer-04`: rerun of pinned copy; report byte-identical to `-03`.

Originals/full SRAM remain outside Git. Renode main was not rerun for this test. Product fulfillment remains 13/29, 44.8%. Integrated main, 576×288 screen, and actual installation/recovery remain incomplete.

Next trace message types/callers connected to actual screen updates and display/ambiqdraw notification producers. First IOM6 SPI contract and normal external font-bank investigation remain separate conditions for full-main progress.
