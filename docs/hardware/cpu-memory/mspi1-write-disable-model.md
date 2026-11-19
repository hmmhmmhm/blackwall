# WRDI and Return from the Original Address-Mode Helper

Task bw-0183. Confirmed the manufacturer WRDI contract and original call, then added release on 04 completion to the optional WEL model. WRDI and the address-mode parent helper returned normally in stock 2.4, 2.3, and Faceclaw originals. Full boot, app loop, and display remained incomplete; product progress was 13/29, 44.8%.

## Contract and change

Page 25 of the SHA-pinned Macronix MX25U25643G v1.1 describes clearing WEL on WRDI 04 completion. Saved requests from the three originals are CFG `03010061`, CTRL C1, instruction 04, data 0 TX. Wrapper entry `47BC28` (stock 2.3/Faceclaw `476F10`) returns the transfer result. On the original parent success path at entry `47BA04`, result 0 leads to return 0. Source was decoded from function entries and compared with actual instruction boundaries.

The exact 04 request is supported only when `EmulateWriteEnableLatch` is selected. On completion it changes only `WriteEnabled=false` and the WRDI counter. Status seed, 4BYTE, and FIFO values are unchanged. WEL is not cleared at transfer start or while incomplete; clock abort preserves existing WEL. Completed 04 also cancels reset-enable. Repeated commands retain WEL 0.

Default option false still rejects 04. Program, erase, NV write, and array read were not added. This is limited virtual latch behavior, not a guarantee of actual NOR state under electrical interruption.

## Test generator defect and fix

The first native unit confirmed that the existing model rejected 04 start as unsupported after WREN and EN4B completed. After the production change, 23 checks with normal seed 40 passed.

In an additional seed-FC test, a global string replacement intended to change expected status also changed MMIO address `40061014` to `FC061014`. Renode logged a read from a nonexistent address and the test failed. After confirming that batch ended and later cases had not run, failure artifacts were preserved.

Separated expected values into explicit placeholders and added AST checks of literal bus addresses in generated setup/phase, rejecting addresses outside the allowed set before execution. Confirmed that the actual previously malformed fixture was rejected and new 40/FC fixtures passed. The first host check expected invalid address `014`, although `00C` was discovered first by ordering, so its assertion failed. In 02 the expected condition was corrected to match the fact that address checking rejected an invalid address.

Compared the existing normal-40 fixture byte for byte with newly generated output and reused it; only the failed NV case was rerun. Original model source was unchanged during this generator fix. The historical WREN checkpoint's “04 unsupported” check remains for its then-current scope; new WRDI checks own current normal 04 handling.

## Original main results

For all three images with option true, observed this sequence:

1. WRDI wrapper returned 0.
2. Original caller returned 0.
3. Address-mode parent helper returned 0.
4. Afterwards the WIP helper read byte 40 and returned 0; polling also returned 0.

The 351 selected events had zero drops and preserved the prior 345-event prefix. WRDI completed once; model WEL=0, status=40, configuration=20, and 4BYTE remained set. There were 1,163 total transfer completions, 1,153 ID, four status, one RDCR, and 1,158 FIFO operations. Not all four status operations were observed in the same WIP helper. The wrapper itself does not read and verify WEL bit. Do not extend the extra byte-40 observation and model state into evidence of physical WEL clearing.

The next strict boundary was read `400612B0`. Execution stopped without supplying a response; it was not passed by returning 0. PC was stock 2.4 `4E92DC`, stock 2.3/Faceclaw `4DBF08`. Meaning and normal idle response were targets for subsequent source analysis.

The option-false control stopped on the original 06 request with zero WRDI completions. Stock 2.3 and Faceclaw used the same model, board, and runtime except for original length. Original bytes, PC flow, branches, and returns were unchanged. Execution began at main reset under existing synthetic memory/power/clock assumptions; this is not full ROM boot or physical behavior verification.

## Evidence and scope

Outside Git under `simulator/`:

- `mspi1-write-disable-unit-01`: functional red where actual 04 start was rejected.
- `mspi1-write-disable-unit-02`, `mspi1-write-disable-nv-unit-02`: 23 checks each for seed 40/FC, covering WEL clear timing, status/NV bits, 4BYTE retention, repetition, abort, reset, and guards.
- `mspi1-write-disable-nv-unit-01`: failed NV fixture and logs with malformed address.
- `mspi1-wrdi-fixture-addresses-02/report.json`: rejection of the old malformed fixture and address checks for both new seeds.
- `mspi1-write-disable-disabled-unit-01`, `mspi1-write-disable-stuck-unit-01`: four checks each; unit total 54.
- `mspi1-write-disable-regressions-01`: address mode 42, fixed busy 22, reset 26; total 90.
- `mspi1-write-disable-main-01`: three originals and disabled control, four combinations.
- `mspi1-write-disable-verification-01/report.json`: 135 checks of current source, manufacturer contract, original bytes, raw markers, fixture addresses, original returns, prior prefix, and default boundary.

Next establish the actual register contract at `400612B0`. Array address handling, NV writes, full boot, display, and recovery success remain incomplete. No physical scan, connection, RAM execution, flash, or persistent write occurred.

An agent inheriting the parent model reviewed production, the address-generation fix, the 135-check audit, and four main results read-only. The discovered NV fixture address-replacement error was fixed with placeholders and preflight and verified blocked using the previous failed input. No additional material evidence gaps were reported. No Astra, other model-family review, or full transcript-file audit was performed.
