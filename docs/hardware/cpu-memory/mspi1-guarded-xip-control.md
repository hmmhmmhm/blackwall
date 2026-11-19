# MSPI1 XIP Control and Unknown-Data Guard

Original main from two stock versions and Faceclaw recorded an XIP enable request and advanced to MSPI INTCLR write `1A80` at `40061208`. No actual flash data was returned and an original flash read had not yet been observed. This is not successful full boot, display, or XIP execution.

## Model

Based on the original NOR caller, DEV0AXI 19, read-only 32 MiB, and MSPI1 window in the [prior contract investigation](mspi1-xip-contract.md), added an optional `BlackwallMspi1XipGuard`. Its default is null, preserving the prior block on XIPEN writes. It does not enable the model simply by filling unknown data.

An enable request is recorded only when:

- The power phase for MSPI1 mask `8000` is on.
- The connected clock gate is on with selection 7/8.
- DEV0AXI is 19: read-only, requested 32 MiB, base `80000000`.
- DEV0XIP bits other than bit 0 match the previously stored value.

These checks validate virtual control inputs. They do not measure physical power, clock frequency, or flash command execution. Connected objects and address mapping were verified on the generated board. AXI configuration changes while active are rejected; repeated enable with the same value increments requests without duplicating transitions. Disable/reset clears control state. Not every DEV0 setting other than DEV0XIP is frozen.

The guard maps the entire 64 MiB MSPI1 range `[80000000,84000000)`. The selected aperture within it is the first 32 MiB, `[80000000,82000000)`; the guard covers the remainder too. **Neither has backing, so every read/write is stopped.** It does not return 0/FF, synthetic fonts, or a filesystem. The same guard stops accesses before enable as well.

DMA/PIO/CQ execution, IRQ semantics, and flash backing were not added. Existing CPU execution memory policy was unchanged. This stage does not provide dynamic evidence of external code execution permission or blocked actual XIP instruction fetch.

## Verification and evidence

Artifacts were preserved under private `simulator/`.

| Artifact | Result and scope |
| --- | --- |
| `mspi1-xip-guard-unit-01` | Failed before implementation because the type was absent. |
| `mspi1-xip-guard-unit-02` | 26 checks with local ready mocks. Covered power/clock, address/size/RO and format, rejection of live AXI changes, four boundaries, blocked byte/word/dword/quad reads and writes, and reset. |
| `mspi1-xip-guard-main-01` | Three originals, non-selected control, and stuck-off: five conditions completed. Each original recorded one enable request/transition and zero guard accesses before stopping at INTCLR write `1A80`. |
| `mspi1-xip-cpu-read-01` | A **separate synthetic M55 guest** aborted on a 32-bit read at `80000000` while enabled. PC `1000C`; the subsequent verification instruction `r2=5A` did not execute. Five checks. This was not original firmware or an instruction-fetch test. |
| `mspi1-xip-config-regression-01` | Passed 67 existing config checks for the default profile. |
| `mspi1-xip-cq-regression-01` | Passed 33 existing CQ initialization checks. |
| `mspi1-xip-guard-verification-01` | 103 checks of the source contract, current model, original bytes/fill, board/runtime/guard inventory, synthetic guest bytes/results, regressions, default, and stuck cases. |

The next PC was `4E8CAA` for stock 2.4 and `4DB8D6` for stock 2.3/CFW. Stock 2.3 and CFW used the same model/runtime except for main length. The non-selected control retained the previous DEV0XIP write `5ED` boundary; stuck-off retained the first DEV0XIP read boundary. Do not interpret stuck-off as a normal fallback.

Only guard inventory and diagnostic output were added to runtime/result so the raw report includes the new guard. Original main, SRAM/ITCM fill, CPU memory policy, and existing execution paths were not forcibly changed.

## Next steps and limits

Next analyze MSPI interrupt clear/enable/status and the NVIC21 boundary. Then observe the PIO/DMA or XIP addresses actually requested by the original and connect the source, hash, and known range of any required backing. Continue stopping on regions without data.

Follow-up bw164: the [MSPI1 interrupt model](mspi1-interrupt-model.md) handled clear/enable and original execution advanced to the Timer14 CTRL read. Distinguish synthetic ISR testing based on software INTSET from observed original status-0 configuration.

A review by an agent inheriting the parent model found no material errors; it incorporated the DEV0XIP format-check scope and distinction between CPU load and instruction fetch. There was no Astra, other model family, full transcript archive audit, or physical device access. Overall product criteria remained 13/29, 44.8%.
