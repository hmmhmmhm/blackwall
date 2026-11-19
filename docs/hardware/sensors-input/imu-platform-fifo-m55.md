# FIFO transport in original RTOS context

bw470. On the full stock 2.4 board, **original FIFO API → platform callback → mutex/IOM preparation → HAL → actual I²C FIFO → IOM cleanup/mutex release → original parser/callback → sample storage** was verified. Bus and kernel functions were not replaced with stubs. This is a diagnosis inserting a synthetic API caller at a stop after main reset, not completed natural main sensor acquisition. E12 remains partial; overall 10of16=62.5%.

## Boundary changed from the previous test

The standalone SRAM in [bw469](imu-hal-fifo-m55.md) represents the moment the IOM mutex is locked: mutex slot 0x20076068 → queue 0x20007a70, count 0, owner Sensor task. Calling the upper API unchanged would not properly test the lock lifetime.

At existing full-board getter breakpoint 0x5542c6, the original mutex has count 1 and owner 0. A new reset run reproduced this state. Initial full SRAM was exact against existing `imu-fifo-i2c-cold-on-final-01`; main/model/board and existing observation code were unchanged. New observation hooks were added only after this stop.

Original memcpy signature was then verified and a synthetic caller copied to an empty 512-byte ITCM area. It used the original Sensor task Thread/PSP and stack; the host did not change SP, TCB, IRQ mask, or sensor gate. Guest MRS yielded PRIMASK0/BASEPRI0/CONTROL6/IPSR0. Host register index 22 is not interpreted as architectural BASEPRI.

The two bytes frame size 16/endian 0 and two virtual raw16 packets are explicit test inputs, not claimed to arise naturally from sensor initialization. Ring/header were not prepared by the host; their original zero state was used.

## Actual original calls

Synthetic caller invokes FIFO API 0x552f7c. Original code reads register 0x12 twice in count helper and data 0x14 once. Each read passes through:

1. platform callback 0x4c2186 → I²C helper 0x551a62.
2. mutex acquire 0x442f08 → IOM/pad preparation 0x55183e.
3. HAL 0x5820d8 twice for register select and receive.
4. IOM cleanup 0x5518ba → mutex release 0x442f6e.

After three transactions the API returned 0 and provided count 2 and 32-byte payload. The FIFO adapter consumed two packets and completed three transactions. Mutex returned to count 1/owner 0; start/end SP and current TCB matched.

The parser caller reads actual count output and invokes original 0x552fa6. Registered callback 0x4c4c6c executed twice and parser also returned 0. Independent audit calculated and compared expected values for all 2252 ring bytes, including raw axes, bias/scale float conversion, mode-table timestamp, flags/index, and unused slots.

This advances beyond a direct HAL caller to the original platform and kernel path. It does not yet establish upper consumer 0x4c38b0 status lookup, GPIO38 IRQ/task dispatch, natural creation of gate 1, or full sensor initialization success. Gate remained 0.

## Controls and limits

Three final positives are API only, with parser, and parser without observation hook. The last control removes only intermediate function Watch hooks and retains the completion stop hook. Final SRAM 3.5 MiB and WORK 64 KiB were exact between the two parser runs. This compares those final memory regions for this input; it does not guarantee no effect on all registers, virtual time, transient writes, or all hooks.

All three positives jointly confirmed completion marker/original return 0, expected payload, lock restoration, gate 0, and guard/CPU fault 0. Saved audit passed 61 judgments; four owned containers were confirmed journal removed and absent in Docker inspect. This new connection remains unverified for stock 2.3/Faceclaw.

The first run specified the wrong test-copy entry and executed another original function. The failure, with unmapped-write warning, missing completion marker, and FIFO consumption 0, is preserved. Guard/fault 0 alone could not establish success. For the rerun, the unique original memcpy byte signature used by existing tools was checked to find the address. Original/model were unchanged and the failure is not used as a normal result.

## Evidence and next steps

Outside Git, `simulator/imu-platform-fifo-research-01` contains `run-board.py`, `audit.py`, `audit.json`, frozen source, and preparation records. Runs are `imu-platform-fifo-m55-01` (failure), `-02` (API), `imu-platform-fifo-m55-parser-01`, and `imu-platform-fifo-m55-parser-no-watch-01`. Full file hashes are pinned in `imu-platform-fifo-m55-manifest.json`.

```sh
<private-python> <research>/run-board.py <new-private-output>
<private-python> <research>/run-board.py <new-private-output> --parse
<private-python> <research>/run-board.py <new-private-output> --parse --no-watch
<private-python> <research>/audit.py
```

Next connect FIFO status/IRQ, guest flush, and device lifetime to the actual original consumption path. The normal GAF computation contract remains missing. This result does not justify arbitrary ready, branch, or gate changes. No physical access, firmware installation, subagents, or external publication.
