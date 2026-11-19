# State-Unchanged Writes to Unconfigured GPIO

## Scope and evidence

bw-0237. The initial hypothesis that GPIO output latch and pad configuration are always independent was not adopted. Pinned GPIO metadata says WT/WTS/WTC update when output is enabled, so changes to unknown pad state are not generally allowed.

Optional `gpioOutputIdempotentWrites` allows only writes that do not change bits already stored in the model. This is limited reasoning that both outcomes for that bit are the same even if enable status is unknown. Initial latch 0 is an existing synthetic initial state, not proof of actual device WT initial state. Pad voltage, direction, and electrical behavior are not implemented.

Reserved-only pins reject even unchanged writes. Mixed masks are validated completely before atomic handling; if an unknown bit would change, the entire write is rejected. Existing mux/output/force conditions and default strict behavior remain. No PINCFG values are fabricated.

## Verification results

- Pinned HAL/header/metadata and 12 original GPIO function runs, 29 contract checks.
- After confirming red for the unimplemented option, 29 native unit checks passed.
- Observations in 23 default-policy regressions reusing existing ELF/board/probe exactly matched prior results.
- In three original mains, after two unchanged writes to pin136 and pin93, original code directly wrote `0x183` to both PINCFGs. Final latch is `[0x600,0,0,0,0x200040,0,0]`.
- Stock 2.4 option-off control matched existing CPU, instruction count, observations, and GPIO136 strict stop.
- 901 host audit checks bundling saved inputs, model, execution logs, and reports passed. Check count is not product completion percentage.

Next boundary is PWRCTRL.DEVPWREN `0x40021004` write. Stock 2.4 and CFW request `0xe80`; stock 2.3 requests `0x8e80`, whose `0x8000` is the MSPI1 request bit. All include new IOM6 request `0x80`, but the full request words are not interpreted as identical. PC is respectively `0x494d78` and older/CFW `0x488e90`.

UART transmit bytes, IRQ8, and previous event prefix were retained against each input's baseline. This does not establish full-path/schedule equivalence across inputs or actual pad behavior.

## Evidence and next scope

Code: `tools/renode-strict-mmio.cs`, `tools/verify_gpio_unchanged_writes.py`, `tools/inspect_gpio_unchanged_contract.py`, `tools/gpio-unchanged-candidate.json`.

Private simulator outside Git: `gpio-unchanged-contract-01`, `gpio-unchanged-unit-01`, `gpio-unchanged-regression-01`, `gpio-unchanged-main-01`, `gpio-unchanged-verification-01/report.json`. Run the audit as `audit.py <private-simulator-root>`; it reads saved evidence without rerunning native.

Next candidate investigates IOM6 request, status, and initial transfer together using existing shared-power/IOM engines. Peer identity and response are not yet assumed. Normal font-bank/integrated display, full boot, web virtual installation/recovery, and real-device verification remain incomplete. Overall remains 13/29=44.8%.
