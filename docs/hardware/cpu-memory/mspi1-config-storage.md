# MSPI1 Initialization Configuration Storage

Original main from stock 2.4/2.3 and Faceclaw performed 13 MSPI1 configuration reads and 20 writes, then stopped at write 0 to `0x400612C0`. The public MSPI register at this address is CQCURIDX. MSPI transfer, CQ engine, and display output had not yet executed.

## Model scope

Used pinned official Apollo DFP 1.6.0 SVD and header from HAL `61b293a49db34030c545f99101f7ebf6a3050314`. `inspect_mspi1_config_contract.py` compares field masks for 43 MSPI0 registers and 43 M55-target offsetof values. Code also verifies MSPI1 inheritance from MSPI0 and base `0x40061000`. Overall root-source provenance follows `adc-software-scan-research.md` and `mspi1-clock-control.md`.

Selected only 25 configuration registers for source-reset storage. They include CTRL1/ADDR/INSTR/THRESHOLD, pad configuration, DEV0 configuration group, DMA address/count/threshold, and disabled DMACFG. Actual memory transfer and pad electrical behavior are not implemented.

- MSPICFG's upper three reset-control bits must retain initial `C0000000`. FIFO/reset state changes are blocked.
- XIPEN, DMAEN, and scrambling enable must be 0. Storing addresses/options differs from executing XIP/DMA.
- CTRL, FIFO, TX/RX entries, status, IRQ, and CQ remain strict for both reads and writes. An SVD read-write label alone is not grounds to model FIFO or status as simple storage.
- Power phase must be on for configuration access. Off/stuck-off stops at the strict guard without changing values or read/write counters.
- APB configuration storage independent of the IO clock gate is a virtual contract, not a measurement of physical accessibility.
- The low fixture owns and resets the state; high/tail guards delegate to the same owner. An optional interface avoids making existing model builds depend on a new implementation file.

## Evidence

- Private `mspi1-config-contract-01`: field masks and offset compilation for 43 public MSPI0 registers and the 25-item configuration list. MSPI1 inheritance is also checked directly by the later current inspector and final audit.
- `mspi1-config-unit-01`: failure due to unimplemented type. `unit-02`: 67 checks passed with a local ready-input mock. Covered power-off, reset, behavior bits, and other strict registers/widths.
- `mspi1-config-main-01`: five conditions completed. Each active original performed 13 reads/20 writes then CQCURIDX write 0. PCs were stock 2.4 `572BAE`, stock 2.3/CFW `555C5A`. This is neither a cross-version performance comparison nor evidence of a normal app loop.
- The unselected control retained the previous DEV0XIP read at `40061090`. Stuck-off stock 2.4 was blocked by the model on the same first read, preserving zero config reads/writes and initial values. This is a model boundary, not the original's safe fallback.
- `mspi1-config-verification-01`: directly compared the current 25-item model table with pinned metadata and audited unit/original/board/runtime/fill/default/stuck in 79 checks. Source reset was not determined merely by reading back the unit's own values.
- `mspi1-config-clock-regression-01`: reverified 16 existing clock unit checks on current core. An earlier board without the optional model also built.

As in previous work, original ARM main bytes were unchanged and only runtime observation output was added. Full boot, integrated display, and physical-device/safe-recovery verification remain incomplete. Next investigate CQ initialization, execution start, and original transfer requests. Use panel candidates in the [G1 decomp review](../../research/even-realities-decomp-review.md) as auxiliary material without establishing the actual MSPI1 peer from them.
