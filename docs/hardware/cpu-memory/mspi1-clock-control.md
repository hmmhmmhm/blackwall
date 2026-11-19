# MSPI1 Clock-Control Storage Model

## Design and evidence

The first access after the existing MSPI1 power response is `0x40004110`. Compared public CLKGEN `MSPIIOCLKCTRL` base/offset with original ARM literals and read context. The original is on a path updating the selection field for module 1, selection 8, and setting enable. This static interpretation and observation of actually completed writes are separate evidence.

Previously preserved [Ambiq Apollo DFP 1.6.0](https://download.ambiq.com/packs/AmbiqMicro.Apollo_DFP.1.6.0.pack) `apollo510.svd`, SHA-256 `a2390c3366450eaccc9d4531d26dc9d68488ec42de5795ee50ab45a266f28276`, specifies reset `0x000A4214` and mask `0x000FFFFF`. The pinned header is `apollo510.h` from HAL commit `61b293a49db34030c545f99101f7ebf6a3050314`. Evidence that the official pack assigns the same SVD to Apollo510 Blue differs from confirming exact silicon/reset on actual G2. Do not assume redistribution rights for the entire pack; originals remain outside Git.

Selected a `source-reset-storage` profile using public reset rather than supplying synthetic initial zero. Full clock-engine implementation was excluded because its need and peripheral connections had not yet been established. The current adapter does not generate an actual clock.

## Contract

- Only MSPI1 selection bits `[9:6]` and enable bit 5, mask `0x3E0`, may change.
- Only selections 7/8 specified by public SVD are allowed. HFRC 96/192 MHz respectively are **source labels**, not evidence of actual execution frequencies.
- Other modules and reserved bits must retain initial values. Violations stop at the strict guard before writes, counters, or power state change.
- As CLKGEN storage, access itself does not require MSPI power-ready. Successful storage while power is off does not establish physical bus behavior or safe failure handling.
- Byte/halfword access and MSPI controller MMIO remain strict. Reset is delegated by the fixture owner to the adapter.
- Connected through an optional interface; an unselected profile retains the existing board and stop boundary. Building existing fixtures does not force dependency on the new implementation file.

## Verification

`tools/inspect_mspi1_clock_contract.py` checked source pins, eight field masks, reset, M55-target compiled offset, and three original ARM read contexts in 26 items. Saved privately at `simulator/mspi1-clock-contract-01`.

Unit01 of `tools/verify_mspi1_clock.py` failed due to an unimplemented type. Unit02 passed 16 checks of reset/read/write, enable/disable, select 7, preserving other modules, rejection of reserved/invalid selection/width, no power side effects, and owner reset. This unit fixture is distinct from original firmware evidence.

All five conditions in `mspi1-clock-main-01` completed. Original stock 2.4/2.3 and Faceclaw 38 showed two reads/two writes, value `0xA4234`, selection 8/gate on, then stopped strictly on a 32-bit read at `0x40061090`. PCs were 2.4 `0x4e7186`, 2.3/CFW `0x4d9db2`. The public SVD identifies this address as MSPI DEV0XIP configuration, but an attempted access alone proves neither XIP execution nor an actual flash peer.

The unselected control retained the prior `0x40004110` read boundary. Stock 2.4 stuck-off retained status 0 while attempting the same clock writes and `0x40061090` read. Normal power-failure handling or fallback was therefore not established.

`mspi1-clock-verification-01` checked 78 items including original bytes, full model, board derivation, observation-only runtime, fill preservation, full unselected boundary, and stuck power state. `mspi1-clock-power-regression-01` reverified 23 existing power unit checks on current core with the new optional interface, including a path where an earlier board compiles without the separate implementation file.

An inherited-parent-model review found no material logic error. No other model-family review or transcript-archive audit was performed. There was no Astra or hardware access. Full boot, app loop, integrated display, and physical clock/MSPI remained unverified; product progress stayed 13/29, 44.8%. Next investigate the boundary between MSPI initialization configuration registers and actual transfer side effects.
