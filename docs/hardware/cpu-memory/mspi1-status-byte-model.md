# Explicit NOR Status Values and Original Idle/Busy Paths

Task bw-0178. Implemented one-byte RDSR 05 reception from a selected virtual status byte. Compared idle paths in original stock 2.4/2.3 and Faceclaw, fixed busy fault input in stock 2.4, and an unspecified-status control using original ARM main. Full boot, app loop, and display remained incomplete; product progress was 13/29, 44.8%.

## Default behavior with unknown status

`statusByte` in `BlackwallMspi1PioReset` defaults to -1 (unknown). Only an explicitly selected 0..255 byte and MX25U25643G identity handle INSTR 05, CTRL `10441`, DEV0CFG `03010061`. Default unknown and identity-none generate no status response. Explicit 0 is also a valid test input.

The value is an immutable fixture. Only after transfer completion does FIFO contain one status byte and model padding 0 in one word; status completion count is separate from ID completion count. FIFO, clock-change abort, owner reset, transfer delay, and unread-frame guard remain. Owner reset clears FIFO and counters but does not change the supplied fixture byte.

Thus `statusByte=65` is a **fixed stuck-byte fault input** that stays the same after reset. It does not reproduce actual NOR program/erase, dynamic WIP/WEL transitions, reset semantics, or nonvolatile registers. Actual glasses' QE/protection bits or current WIP were not observed. WREN, program, erase, status write, and flash backing were not implemented at this stage.

## Execution results

`0x40` and `0x41` have the same QE bit and differ only in WIP. Both were used to avoid an incorrect judgment that succeeds only when the entire status is zero.

| Original main and input | Status receives completed | Observed WIP helper return | Poll return | Next stop |
| --- | ---: | --- | --- | --- |
| Stock 2.4 / 40 | 1 | 0, once | 0, once | INSTR 06/CTRL C1 request |
| Stock 2.3 / 40 | 1 | 0, once | 0, once | Same request |
| Faceclaw / 40 | 1 | 0, once | 0, once | Same request |
| Stock 2.4 / 41 | 2401 | 1, 2400 times | 1, twice | MMIO `400612B0` read |
| Stock 2.4 / unknown | 0 | Not reached | Not reached | Existing 05/RX1 request |

Values 40/41 are hexadecimal. In all three idle runs the original WIP helper actually read 40 from RAM and returned 0, then original polling also returned 0. Under busy, each of two polling intervals contained 1,200 nonzero helper returns. After both failures, execution entered a different subsequent path from idle. One of the 2,401 total status reads did not correspond to a registered WIP-helper-return observation; its role was not determined here.

The next busy PC is `4E92DC`, read address `400612B0`; this unimplemented request remains blocked by a strict guard. Idle's next 06 was not yet handled either. Unknown control retained the same strict boundary as prior bw176.

All mains ran the same pinned ARM bytes from main reset. Branches, function returns, and delays were unchanged. Existing synthetic memory/power/clock and other assumptions still apply. Do not extend this to passing all actual hardware checks, full ROM boot, or normal physical startup. Stock 2.3 and Faceclaw retained the same model, board, and runtime except for original length.

## Observation failure and reuse

The first busy run naturally reached the strict boundary, but 5,133 observation events exceeded the 4,096 limit and 1,037 were dropped. The tool failed it rather than producing a success report. Raw logs and snapshots were preserved.

Reobservation retained model, board, and main while removing repetitive byte observation points, recording helper results and polling returns only. The first RAM byte snapshot was read at the helper-result observation point. Busy had 2,733 events, zero drops, and the same final PIO state and strict boundary as the first run. Three already successful idle runs were not rerun. The same follow-up batch checked unknown control. This narrowed read-only observation scope; it did not change guest state or parser safety conditions.

The regression harness batch failed because it compared reset fixture 03's actual 23 items against an incorrect expected 26. Reused earlier successful RDID 30 and zero-turnaround 36 results and separately ran only correct reset fixture 05's 26 items. Failure artifacts were also preserved. A dict/list concatenation error found while writing the main tool was separately fixed by splitting report fields before main execution.

## Verification and preservation

Outside Git under `simulator/`:

- `mspi1-status-unit-01`: red evidence that the old API did not accept statusByte, distinct from a transfer-rejection test.
- `mspi1-status-unit-02`, `mspi1-status-busy-unit-01`, `mspi1-status-zero-unit-01`, `mspi1-status-ff-unit-01`: 22 checks each for 40/41/00/FF delivery, FIFO, abort, reset, and separation from existing ID.
- `mspi1-status-unknown-unit-01`, `mspi1-status-none-unit-01`: four checks each.
- `mspi1-status-stuck-unit-01`: ten incomplete-transfer checks, a controller-stuck scenario distinct from fixed WIP busy.
- First two child reports of `mspi1-status-regressions-01` and `mspi1-status-regressions-02`: reused 66 + separate 26 = 92 checks.
- `mspi1-status-main-01`: three successful idle runs and raw busy evidence with observation overflow.
- `mspi1-status-main-02`: compact busy reobservation and unknown control.
- `mspi1-status-verification-02/report.json`: 161 checks of current source, original bytes, fixtures, raw markers, observation runtime, original results, and controls. Audit 01's 160 checks remain; 02 directly compared the two 1,200-return polling intervals against raw events.

Check counts are neither product progress nor physical-device validation counts. Next analyze the 06 command on idle or `400612B0` access contract on the busy-failure path. This is not authorization for physical firmware persistent writes. There was no physical scan, connection, RAM execution, installation, or persistent write.

An agent inheriting the parent model reviewed production, unit tests, saved audits, and observations read-only, reporting no additional material defects. Actual NOR dynamic state and the complete error/recovery path after busy remain unverified. No Astra, other model-family review, or full transcript-file audit was performed.
