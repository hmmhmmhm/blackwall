# Handoff verification for recovery boot and Faceclaw main

Status: emulation of the pre-transfer path passed. This is not normal boot, physical compatibility, or installability.

## Inputs and method

`tools/emulate_combined_handoff.py` pins exact SHA256 for the complete 2.4 research boot, Faceclaw/38 main component, and stock 2.4 main component. It also checks main preamble, vectors, and range. Originals and result JSON remain outside Git.

After executing actual stock data-initialization code, main is placed at 0x438000. Execution starts at each patched call site 0x42e3e4 and 0x42e450 with R0=0x438000. Actual patch boot_handoff (0x434b2c) and actual stock vector handoff (0x42dfe8) execute. There are no function stubs; only system-register space is mapped as emulator memory. Execution stops immediately before main's first reset instruction.

Four conditions were run for each main/hook: no selection record, valid main selection, corrupt complement, and out-of-range selection. All 16 passed. Four corruption controls replacing BL with two NOPs for each main/hook were all rejected.

| Main | Reset entry (excluding Thumb bit) | Initial SP | VTOR |
| --- | --- | --- | --- |
| Faceclaw/38 | 0x601a3e | 0x2007fb00 | 0x438000 |
| Stock 2.4.0.24 | 0x5fbe3e | 0x2007fb00 | 0x438000 |

All three words in one-shot selection area 0x2007cff0 were initialized to `(0, 0, 0xffffffff)`. The only observed system-register write was one VTOR setting. Report: private `boot-2-4-analysis/combined-handoff-02.json`. The first report remains as a pre-corruption-control record.

## What this result does not prove

- Normal arrival at this hook in the full boot flow: R0 and call location were specified at test start.
- Compatibility of main initialization and scheduler, interrupt, watchdog, and peripheral state: reset instructions onward were not executed.
- Codec/NOR resource compatibility during Faceclaw execution: notably 2.3 and 2.4 codec payload differences remain.
- Physical power interruption, reboot, recovery, and full-stock restoration.

This result neither adds a requirement that main and boot versions match nor permits arbitrary mixing. It verifies a limited handoff path for specific current candidates. The web installation gate remains.
