# Missing-font-asset diagnosis and subsequent original main initialization

Work bw-0220. **This mode does not implement normal fonts or normal stock boot.** With actual XIP font-bank unavailable, it is an explicit diagnostic of how far original header-error handling proceeds. Overall goals of web installation, recovery boot, and integrated ARM simulator remain.

## Original execution performed

Stock 2.4.0.24, 2.3.0.24, and Faceclaw 38 ran from original main reset in low-role scenarios. Each reached both header magic-check failures, descriptor clearing, font initialization return, nonnull returns from both chain builders, and font-manager epilogue once. Internal branches, PC, original files, and function returns were unchanged. All existing event prefixes were preserved.

| Input | Font diagnostic reads | Next PC | Next strict access |
| --- | ---: | --- | --- |
| Stock 2.4 + diagnosis | 2 | `0x494d78` | 32-bit `0x600` write to `0x40021004` |
| Stock 2.3 + diagnosis | 2 | `0x488e90` | Same |
| Faceclaw 38 + diagnosis | 2 | `0x488e90` | Same |
| Stock 2.4 default | 0 | `0x47605a` | Existing `0x80100000` 32-bit read blocked |

In all three diagnostic runs r0 was FFFFFFFF at original error-branch entry, observed RAM after descriptor store was 0, and r0=1 at font initialization epilogue. Both chain-builder returns were aligned SRAM pointers. This is not extended to successful use of all glyphs or font-chain traversal. Font manager passed original epilogue and reached a subsequent initialization power write.

Default mode exactly matched previous CPU, device report, instruction count, and all observed events. Each diagnostic's next boundary was one MMIO guard without memory execution-policy violation. Original next instruction is `str r1,[r0]`, actual registers r0=40021004, r1=600. The write was not applied. Identifying bit meanings and HAL caller for that shared power register is next.

## Limited mock response contract

Optional profile `missing-font-magic-only` was added to existing `BlackwallMspi1XipGuard` in `tools/renode-mspi1-config.cs`. Default is null and all XIP bytes remain unknown. Tool comparison confirms changed code in the full model is limited to this guard and immediately preceding explanation.

Diagnostic returns 32-bit FFFFFFFF only if:

1. Explicit profile and two distinct source-confirmed original read PCs are specified.
2. XIP is enabled and existing power/clock readiness conditions are met.
3. First read is offset 100000, first PC, R4=80100000.
4. Second read is offset 700000, second PC, R4=80700000.
5. CPU bus context is Cortex-M and both reads occur once each in that order.

These are not device-read values. They are two invalid magic words selected to reproduce header errors; no other NOR bytes or coherent flash image is supplied. Equal values do not imply the full flash is erased. Repeated XIP enable/disable does not restore read budget; only explicit model reset does.

Other offsets, PCs, R4, host bus reads, byte/word/quad accesses, writes, rereads, or second header first are rejected. Instruction fetch cannot satisfy reviewed data-read PC and R4 conditions; existing executable-memory policy was unchanged. Public `TryReadMissingFontHeader` is an entry point for direct contract tests; actual bus entry separately checks CPU context.

Renode did not auto-inject optional IMachine argument, causing initial fixture creation to fail. IMachine was made a required constructor argument so default boards also inject it. Existing board power/clock specifications remained and default-mode regression was verified. Direct constructor calls in the project were updated too.

## Verification

- TDD red: first magic-read check failed without mock response in `missing-font-header-red-02`. `red-01` was a fixture failure from constructor injection and is not behavioral red evidence.
- 33 direct contract/rejection checks: `missing-font-header-unit-01`.
- 26 existing XIP control/unknown-byte checks: `missing-font-xip-regression-02`. Original builder rejected before execution because old verifier's frozen root prefix differed from current root. `--legacy-control` ran existing DRIVER and board against current full model. Protective assertions were not deleted and old model was not reported as current verification.
- Three synthetic M55 CPU cases: normal PC/R4 executes one read and subsequent marker; wrong PC or R4 stops at guard without marker. `missing-font-header-cpu-01`. This is context-gate testing, not original firmware execution.
- Four original main cases and 97 source/log/input audit checks: `missing-font-header-verification-01/report.json`.

All results are outside Git under `simulator/`. Model source, original main file, and derived-input hashes were checked. Native Docker ran sequentially and exit was confirmed. No device scan, connection, RAM execution, or persistent writes.

## Reproduction tools

`tools/probe_missing_font_main.py` does not enable diagnosis by default; `--missing-font-magic` is required. It accepts `--case stock24|stock23|cfw`, `--role low|high`, but this original diagnostic evidence comprises three low cases and stock24 default control. Do not generalize to high or actual left/right temples.

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/probe_missing_font_main.py \
  "$HOME/Library/Application Support/Blackwall/simulator" \
  "$HOME/Library/Application Support/Blackwall/simulator/new-missing-font-run" \
  --case stock24 --missing-font-magic
```

Use a new output path. The tool validates original input and runs in a separate directory; it is not a physical installation tool. Verification tools are `verify_missing_font_headers.py`, `verify_missing_font_cpu.py`, and `verify_missing_font_evidence.py`.

## Remaining scope

The [existing null-descriptor glyph error](xip-font-resource-contract.md) remains. Initialization progress before glyph drawing is confirmed; actual font pixels, CJK assets, framebuffer, and lens transfer are not verified. This is not a substitute for completing a simulator with normal font assets.

Next identify original HAL contract for the new power write and required peripherals. Actual font-bank acquisition and normal-display verification are also separately needed. Integrated boot/screen output remain incomplete; overall conditions 13/29, 44.8%.
