# Functional Instruction-Memory Model and Cache Boundary

Status: resolved a cache-handling difference between two engines exposed on OFF/LP paths. Default execution stops immediately at the first ICIALLU write. With a separate functional model selected, 12 combinations of two stock versions and Faceclaw, OFF/LP and LP/HP, stop at the same next address. This does not verify physical cache, full boot, firmware display output, or installability.

## Confirmed cause and sources

Original firmware checks the CCR IC bit and executes barrier → ICIALLU write → barrier → IC set. Compared with pinned public sources:

- [CMSIS 6.3.0 core_cm55.h](https://github.com/ARM-software/CMSIS_6/blob/45dab712ad84f8cbbf2b7bfc089c19088507df6f/CMSIS/Core/Include/core_cm55.h): SCB/MEMSYSCTL structures and IC bit 17.
- [CMSIS SCB_EnableICache](https://github.com/ARM-software/CMSIS_6/blob/45dab712ad84f8cbbf2b7bfc089c19088507df6f/CMSIS/Core/Include/m-profile/armv7m_cachel1.h): ICIALLU=0 followed by CCR.IC enable.
- [Renode NVIC reference source](https://github.com/renode/renode-infrastructure/blob/042a58285ee91453f99d31f19e8aa140102ec540/src/Emulator/Cores/Arm-M/NVIC.cs): CCR forwarding and ICIALLU offset.

Verified CMSIS tag commit, Git blobs, and SHA-256. Compiled extracted structures with Cortex-M55 Clang and verified CCR offset `0x14`, ICIALLU `0x250`, and PFCR `0x4` using `_Static_assert`. NVIC reference-source SHA-256 is `163b01c7e1b55ca5c22c59da4a80b1455961e1adc7a0fb7272b9ea791069168e`. It was not established that this reference was the exact build source of the portable Renode executable. Observed executable behavior and actual API tests were verified separately.

Previously Renode issued an unhandled ICIALLU warning and continued, then warned that enabling IC was unsupported. The result failed because of warnings, but did not stop on the first unsupported access. `BlackwallSystemControl` is now attached by default and blocks that write before NVIC handling. It is not arbitrarily ignored or classified as successful despite warnings.

## Optional functional model

`--coherent-icache-model` defaults OFF. When ON, instruction memory is treated as the engine's coherent shared memory and only these controls are supported:

1. DWORD ICIALLU=0 records an invalidation count.
2. CCR.IC may be set after invalidation. Clearing it and repeated invalidation are also supported.
3. Changes to CCR bits other than IC, D-cache enable, invalid widths/ICIALLU values, and reads are rejected.

Renode handles ICIALLU as an explicitly defined register and stores the IC bit in the model. Only IC is removed from CCR writes forwarded to the CPU, avoiding unsupported cache-enable requests while preserving other CPU control bits. Reads reflect logical IC state. This is not relaxed warning filtering.

Unicorn connects the same controls to its existing CPACR/CCR adapter. Using the option in that engine also requires explicit CPACR storage and cache-off initial conditions. The report's CCR display value updates immediately after writes as well as on reads.

There is no separate physical I-cache. Cache latency, replacement, power, aliases, and DMA coherency are not modeled. Physical completion time of barriers was not verified. This is functional testing in one isolated execution and does not guarantee reset, TrustZone, or multicore accuracy.

## Verification

Passed 116 Python regressions and 13 synthetic Renode tests. The same C guest was compiled/executed in 13 modes on Unicorn too. Those 13 modes are subcases inside one Python test and are not double-counted as 13 separate Python tests.

Checks include enable/disable/repeated invalidation, missing prerequisite invalidation, wrong value/width, reading a write-only command, and rejection of D-cache and other CCR bit changes. Default OFF also stops at the first command. A Renode test with memory policy attached blocked execution of an incomplete Thumb-32 instruction.

Code visibility was checked by actual execution: write and run an ITCM function returning 7, then with IC enabled modify its instruction to return 9 and invalidate. Both engines returned 9 on the next run. This is a code-change test at that virtual address, not proof of all cache/memory coherence or actual hardware behavior.

Actual-main comparison covered three images × main LP/HP × buck OFF/LP = 12 combinations. All matched:

- Identical original main hash and next stop PC/address/width.
- IC enabled state, one invalidation, one CCR write, and read count.
- Values and read/write counts for 12 public trim-fixture words.

The next access was a `0xe001e004` MEMSYSCTL.PFCR write, which was not allowed. No Renode memory-protection violations or unexpected warnings occurred. Stock 2.4 OFF with the option disabled stopped at the same `0xe000ef50` write as Unicorn, and the ACT path retained the existing VREFGEN4 stop. This regression covers one stock 2.4 LP combination and must not be extended to all paths.

## Reproduction and material

```sh
"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/verify_renode_icache.py \
  "$HOME/Library/Application Support/Blackwall/simulator/new-icache-verification"

"$HOME/Library/Application Support/Blackwall/simulator/venv-02/bin/python" \
  tools/firmware_runner.py \
  "$HOME/Library/Application Support/Blackwall/simulator/inputs/verified-01/stock-2.4.0.24.bin" \
  --scenario startup-zero-info1-rev-23-buck-off-coherent-icache-hypothesis \
  --output "$HOME/Library/Application Support/Blackwall/simulator/new-coherent-main.json"
```

For buck LP, change `buck-off` to `buck-lp` in the scenario name. Renode main execution adds `--coherent-icache-model` to existing memory-LDO/buck-state conditions. Use a new output path. Pinned originals and analysis remain outside Git.

Private simulator material:

- `coherent-icache-source-audit-01/`, `upstream/cmsis-6.3.0/`: provenance and offset checks.
- `renode-icache-verification-01/`: 13 synthetic guest cases.
- `coherent-icache-main-comparison-01/`: actual-main comparison across 12 combinations.
- `renode-icache-stock24-off-*-01/`: initial tests of default blocking and functional model.
- `coherent-icache-final-review-01/`: final Python regression and ACT-preservation checks.

Next analyze PFCR configuration and subsequent memory-system controls. Preparation of web-installable CFW/recovery boot and the full boot/display integration goal remained in progress. All boot/hardware/installable verification flags were false and actual glasses were not accessed.

Later [PFCR control storage](prefetch-control-storage.md) added cache-geometry selection/read and blocking of unsupported maintenance writes. Initial 13 synthetic cases have expanded to 16 in the current tool; the earlier PFCR-stop profile remains.
