# NOR Status Read and Original Polling Contract

Task bw-0177. Analyzed bw176's saved next request, manufacturer documentation, and original ARM code without changing peripheral source or rerunning main. A status-byte response and busy-branch execution had not yet been verified.

## Actual next request

Requests from stock 2.4, 2.3, and Faceclaw were INSTR `05`, CTRL `10441`, DEV0CFG `03010061`, one-byte receive, no address. These were confirmed in actual stack descriptors and strict MMIO requests. Decoded sequentially from status-helper and polling-function entries and linked them to call return addresses on the actual stack. Decoding from a literal pool or the middle of a Thumb instruction was not used as evidence.

| Function | Stock 2.4 entry | Stock 2.3 / Faceclaw entry |
| --- | --- | --- |
| Status read and WIP judgment | `47B750` | `476A38` |
| Bounded polling | `47B7E0` | `476AC8` |

The status helper calls the read helper with command 5, no address, and length 1. It reads the received byte only when the transfer returns 0. After `LSLS #31`, a sign branch returns **0 when bit 0 is 0 and 1 when bit 0 is 1**. It does not judge other status bits on this success path. The transfer-error path propagates the transfer return value. Polling checks whether the helper returns 0, so it does not structurally distinguish busy from transfer failure.

The first polling loop checks a limit of C8 (200) iterations; a second loop is bounded by a supplied limit. Both return 0 if the helper returns 0 and return 1 at the limit. Actual time units of the delay function and interaction with the scheduler were not established here, so do not convert loop counts into an exact millisecond timeout.

## Manufacturer status semantics

Compared SHA-256 of the existing pinned Macronix MX25U25643G v1.1 PDF against the source manifest. Page 32 says RDSR 05 can be read during program/erase/status write and outputs the status register after the instruction. Page 36 Table 7 and its explanation describe:

| Bit | Meaning | Model consideration |
| --- | --- | --- |
| 0 WIP | Program/erase/status write in progress | Separate from controller PIO Busy. There is a basis for 0 under an idle NOR assumption. |
| 1 WEL | Write-enable latch | Must reflect actual command state such as WREN. |
| 2..5 BP | Protected region | Nonvolatile configuration; actual device values are unknown. |
| 6 QE | Quad enable | Nonvolatile configuration; do not assume reset made it 0. |
| 7 SRWD | Status-write protection | Nonvolatile configuration; actual device value is unknown. |

Thus an idle fixture with WIP=0 is possible, but there is no basis to say the actual glasses' entire status byte is 0. Do not confuse factory-default descriptions with the state of an already used physical device. The current explicit idle model lacks program/erase/status write and blocks unsupported commands with strict guards. If write commands are added later, also implement WIP/WEL transitions and preservation of original state. Distinguish reset-recovery waiting, PIO transfer completion, and NOR WIP.

## Follow-up model boundary

Supply a status response only from an explicitly selected initial-state fixture, and do not describe it as an actual observation or persistent data. Provide one FIFO byte only on completed transfer; retain existing guards on empty FIFO, overwrite, unsupported lengths/commands, clock changes, and so on. Compare whether the original keeps waiting with busy input and advances along its original path with idle input. Do not turn unknown state into a success value or force original branches.

`simulator/mspi1-status-contract-02/report.json` outside Git, from `inspect_mspi1_status_contract.py`, compares three original requests, helper instructions, actual caller frames, polling bounds, and manufacturer source in 38 checks. Audit 01 also had 38 checks; 02, strengthened through the transfer-failure return instruction, is the final evidence. This is static evidence, not verification of completed status reads, busy-branch execution, full boot, display, or physical recovery.

Overall product progress was 13/29, 44.8%. There was no physical scan, connection, RAM execution, installation, or persistent write.

An agent inheriting the parent model reviewed this read-only. Its finding that transfer errors are also treated as nonzero by the upper loop was incorporated in the interpretation and instruction checks above. No Astra, other model-family review, or full transcript-file audit was performed.
