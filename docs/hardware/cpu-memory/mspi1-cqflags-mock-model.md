# CQFLAGS Mock Input and Original Retention Storage

Task bw-0185. Added explicit virtual handshake inputs so three originals store the full CQFLAGS word in actual state RAM. Controls with changed inputs and unknown blocking were also verified. Actual link, CQ/DMA execution, power transitions, full boot, and display remain incomplete; product progress was 13/29, 44.8%.

## Selected model contract

`cqInputLevels` defaults to -1 (unknown), blocking full CQFLAGS reads as before. Explicit two-bit inputs 0..3 require a CQ initialization profile and PIO signal provider. The values are virtual buffer inputs for the selected peer, not observed actual IOM7 flags or wire values.

The value comprises eight software flags, XOR/XNOR for two buffers, PIO CMDCPL, and current/end index match. STOP and DMACPL remain 0 because CQ/DMA execution is still blocked. The `CommandComplete` interface synchronizes PIO time without increasing guest CTRL read count. Software-only `CqValues` is separate from `LastCqFlags` and the counter for actual full reads.

The source's IOM1READY description ambiguously names IOM0START as the XNOR counterpart. This stage chose a functional assumption pairing each corresponding buffer's SW bit. The source wording is not treated as conclusive evidence of actual hardware wiring. IRQ, pause, fetch, CQ enable, and DMA enable were not implemented alongside it.

IOMSEL 15 (DISABLED) fixes input at 0; full reads are rejected for reserved selections 12..14. The explicit mock vector applies to supported selections 0..11. Unknown retains default read blocking regardless of selection. DISABLED does not make the whole flag word zero: XOR/XNOR of input 0 with software bits and index/completion bits are still calculated.

## Routing boundary improvement

The initial 29 × 4 unit checks and five main cases confirmed explicit mock synthesis, but nonzero mock input was also applied when the unit's reset IOMSEL was 15. This contradicted the manufacturer source rule that the DISABLED signal is always 0. New boundary tests first reproduced the `disabled-route-always-zero` failure.

The model was strengthened, and unit truth tables changed to use normal route 7. DISABLED input 0, reserved rejection, and disabled route after owner reset were additionally checked. The actual selection 7 in the first native main was unaffected, but because source changed the existing artifacts were preserved and five combinations rerun with current source. This rerun verified the modified model; it was not due to an observation timeout.

## Original execution results

| Case | Full reads | Original state RAM snapshot | Next boundary |
| --- | ---: | --- | --- |
| Input 0, stock 2.4 | 1 | `4780` | PWRCTRL `40021004` write `400` |
| Input 0, stock 2.3 | 1 | `4780` | Same request |
| Input 0, Faceclaw | 1 | `4780` | Same request |
| Input 3, stock 2.4 | 1 | `7480` | Same request |
| Unknown, stock 2.4 | 0 | Not reached | Existing CQFLAGS `400612B0` read |

Values are hexadecimal. Known cases had 352 selected events, zero dropped, preserving the prior 351-event prefix. Read-only observation points were placed at original `LDR CQFLAGS` and the instruction immediately after `STR [state+8B8]`; a one-word RAM snapshot was read. Actual source instruction boundaries, state pointer, and SRAM range were checked. The observer did not change PC, branches, return values, or RAM.

The stored values for inputs 0/3 XOR to `3300`, differing only in mock handshake bits; the observed next boundary is the same. This alone does not establish that higher flags are irrelevant in every future firmware path or actual wiring. Original restoration using only low eight bits was established by earlier source analysis; **restoration execution was not observed in this work**. Power off/on success and full retention completion were not proven either.

Default unknown `LastCqFlags=0` is an initial diagnostic value with zero successful full reads, not a response. No 0 was returned to an actual read. Stock 2.3/Faceclaw have the same model, board, and runtime apart from original length. Existing synthetic memory/power/clock main-reset assumptions continue to apply.

## Evidence and verification

Under `simulator/` outside Git:

- `mspi1-cqflags-unit-01`: red because the old API did not accept cqInputLevels.
- `mspi1-cqflags-routing-red-01`: actual failing fixture before routing-rule improvement.
- `mspi1-cqflags-unit-03`, `mspi1-cqflags-input1-unit-02`, `mspi1-cqflags-input2-unit-02`, `mspi1-cqflags-input3-unit-02`: 33 checks each. Covered all two-bit inputs and SW combinations, index, completion/W1C, guest-read side effects, and routing boundaries.
- `mspi1-cqflags-unknown-unit-02`: four unknown-blocking checks. Unit total: 136.
- `mspi1-cqflags-regressions-02`: CQ init 33 and WRDI 23, total 56.
- `mspi1-cqflags-main-01`: preserved original observations before routing improvement.
- `mspi1-cqflags-main-02`: five final-source combinations covering three originals, input 3, and unknown.
- `mspi1-cqflags-verification-01/report.json`: 115 checks comparing source, original bytes, raw markers, routing red/green with identical fixtures, snapshots, counterfactuals, prior prefix, and default boundary.

Next analyze the actual meaning of PWRCTRL `40021004` write `400` and original request conditions. CQ/DMA, array/NV handling, full boot, display, and physical recovery remain incomplete. No glasses access, installation, RAM execution, flash, or persistent write occurred.

An agent inheriting the parent model reviewed the routing improvement, final 115-check audit, and five main results read-only and reported no additional material defects. Actual link, restore execution, and CQ/DMA behavior remain unverified. No Astra, other model-family review, or full transcript-file audit was performed.
