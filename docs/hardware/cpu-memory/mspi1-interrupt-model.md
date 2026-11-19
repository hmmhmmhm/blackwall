# MSPI1 Interrupts and NVIC21

Original main from stock 2.4/2.3 and Faceclaw passed MSPI INTCLR and INTEN handling and advanced to a **Timer14 CTRL `400083C0` read**. Interrupt status was 0 and IRQ line low. This does not prove execution of the original ISR or PIO/DMA completion.

## Source contract

Used `apollo510.h`/`am_hal_mspi.c` from pinned HAL `61b293a49db34030c545f99101f7ebf6a3050314` and official Apollo DFP 1.6.0 SVD. Existing source pins were rechecked.

| Register | Offset | This model |
| --- | --- | --- |
| INTEN | `200` | Stores 14-bit enable mask |
| INTSTAT | `204` | Reads latched status |
| INTCLR | `208` | Clears status bits written as 1 |
| INTSET | `20C` | Sets status bits written as 1 |

All have source reset 0 and mask `3FFF`. The public header's MSPI1 IRQ is 21. Compared HAL enable/disable RMW, enabled-only status masking, status readback after clear, and original clear/readback instructions. The 30 checks in `inspect_mspi1_interrupt_contract.py` verify metadata, 14 fields × four banks, four M55 offsetof values, HAL pins, and static/saved context for three originals.

## Implementation boundary

Connected optional `BlackwallMspi1Interrupts` to `renode-mspi1-config.cs`. Without the profile, prior interrupt MMIO blocking remains.

- IRQ level is `(Enable & Status) != 0`; GPIO connects to NVIC21.
- Clearing one status cause preserves other bits. Setting enable to 0 does not itself clear status.
- Reserved bits, unsupported widths, direct INTSTAT writes, and set/clear alias reads are rejected before values and counters change. Actual hardware semantics of alias readback and direct status writes were not additionally implemented.
- If power is not ready, the upper owner blocks access. Owner Reset initializes status/enable/counters and IRQ line. Distinguish peripheral-source clear/reset from clearing CPU NVIC pending.
- The only status source at this stage is software INTSET. It does not generate PIO/DMA engine completion, error, or FIFO events. Full power-off/quiescence lifecycle was not yet implemented either.

## Execution evidence

Preserved under private `simulator/`:

| Artifact | Result |
| --- | --- |
| `mspi1-interrupts-unit-01` | Pre-implementation failure due to absent type. |
| `mspi1-interrupts-unit-02` | 73 checks: each of 14 bits for masked status, enable/IRQ, NVIC21 pending, clear, separate ICPR; selective clear, atomic rejection, and owner reset. |
| `mspi1-interrupts-cpu-01` | Separate synthetic M55: software INTSET `80` → ISR at vector 37 → INTCLR `80`/marker `5A` → return to thread `10200`. Seven checks; active/pending 21 cleared and guard 0. |
| `mspi1-interrupts-main-01` | Three originals, unselected, and stuck-off: five conditions completed. |
| `mspi1-interrupts-config-regression-01` | 67 existing config checks. |
| `mspi1-interrupts-cq-regression-01` | 33 existing CQ checks. |
| `mspi1-interrupts-xip-regression-01` | 26 existing XIP-guard checks. |
| `mspi1-interrupts-verification-02` | 100 checks of current source pins/IRQ/registers, model, originals/fills, board/runtime, synthetic code/results, regressions, default, and stuck. |

All three originals had INTEN=`1A80`, INTSTAT=0, reads 2/writes 2, and IRQ low. This matches original clear write → status readback → enable RMW. Next PCs were stock 2.4 `5070D4`, stock 2.3/CFW `4E8848`. Execution stopped at the first CTRL14 read in the TIMER bank, separate from existing STIMER.

The unselected control retained prior INTCLR write `1A80`; stuck-off retained the first DEV0XIP read boundary. The latter is a model access block, not evidence of safe original fallback. Stock 2.3/CFW models and runtime were identical except for main length; original bytes, fills, results, and CPU memory policy were retained. Runtime added diagnostics only.

The synthetic CPU test is a separate program with fixed vector/handler and local ready-input mock. It did not substitute the actual original handler or force original PC/returns. Original ISR, physical interrupt, transfer timing, and physical NVIC remain unverified. Following 94 checks in audit 01, six checks reexamining source from current files were added for 100 in 02. Initial artifacts remain.

## Next work

Investigate necessary scope for Timer14 control, counter/compare, and interrupts. Advance original execution to observe actual MSPI transfer, XIP read, and backing-address requirements. Unknown flash remains strict. Full boot, integrated display, and physical installation/recovery conditions remained incomplete; product progress stayed 13/29, 44.8%.

An inherited-parent-model review found no material errors. There was no Astra, other model-family review, full transcript-archive audit, or physical device access.
