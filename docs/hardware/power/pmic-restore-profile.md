# Virtual Read Profile for PMIC Restore Initialization

bw-0136. Requests required by the current original path were grouped and executed under an explicit read-only profile instead of adding arbitrary registers one at a time. No actual glasses were connected or installed.

## Scope and provenance

The pinned Nordic npmx core restore_values path was compared with original ARM initialization. These five queries and seven bytes were actually observed in order on stock 2.4/2.3/Faceclaw:

| Requested register | Length | Declared bytes | Candidate purpose |
| --- | --- | --- | --- |
| 0x0509 | 1 | 00 | ADC configuration |
| 0x050a | 1 | 01 | NTC selection |
| 0x0308 | 2 | 08 00 | Charging current code |
| 0x030a | 2 | cf 01 | Discharge current code |
| 0x0b04 | 1 | 03 | Ship button configuration |

Values are **virtual initial state** researched from pinned ADK reset definitions. They are not actual values inherited by G2 from a prior boot, and actual cold-reset state was not verified. Source is the pinned [Nordic npmx commit](https://github.com/nordicsemi/npmx/tree/4da2753cf47b7fb2cd4443e518eb7b9aaca6fe2f). Root/driver BSD terms are distinguished from separate Nordic-only ADK terms; ADK code itself was not copied, included, or compiled into executable code. Register numbers and behavioral contracts were investigated.

Original current queries differ in data type and conversion from the current public SDK. The original calculates the first code as `2 * ((MSB << 1) + LSB)` and discharge code as `323 * code / 100`. The current SDK's μA API or allowed-code enum is not substituted for the original ABI. The complete unit contract is not claimed established. Actual register transfer and original ARM calculations were retained.

The NTC getter has another path reading beta from scratch registers if the stored restore flag is already set. This query did not appear in the present first-initialization path. Thus this profile is not considered to support reinitialization or every restore branch.

## Model and execution

`BlackwallPmicRestoreProbe` requires explicit profile="source-reset-readonly" for creation. Only the start addresses above and exact read lengths are allowed. Data writes, other addresses, fragmented pointers, and other lengths strictly stop. This is a virtual acceptance condition for pointer write/Finish and read/Finish, not verification of physical ACK, START/STOP, or bus timing. ADC, charging, power, Ship mode, sensors, and IRQ are not implemented. Read history is limited to 16 entries; returned arrays and history arrays are separate.

`tools/probe_pmic_restore_main.py` derives bw134's pinned files. It changes only added peer source, explicit board connection, diagnostics output, and read-only hooks/snapshots. Main, fill, probe, policy, guest PC/registers, and return values are unchanged. It is not automatically connected in the default main runner either.

Unique initialization prefixes, PUSH/POP, direct BL callers, and PMIC instance literals were checked per original. Stock 2.4 initialization is 0x57fdae; stock 2.3/CFW is 0x57cd76. No callback bridge replaced it.

## Confirmed results and next stop

All three originals showed:

- Five pointer writes and five reads, returning seven bytes total, with ten Finish calls.
- Original init entry → return → actual caller continuation observed once each in order.
- Original success status 0x2bad0000 matched at return and caller.
- Actual RAM at caller time confirmed original-written restore flag 1.
- ADC instance snapshot at init return had parent pointer, burst 0, and beta 0.

The last item is actual RAM observation in this virtual initialization path. Beta 0 is not interpreted as a correct sensor setting or actual glasses thermistor value. Subsequent settings and measurements are unsupported. Unlike bw135's pre-store observation, these two snapshots read RAM after the specified original stores.

The original then attempted to write byte ff to register 0x0005. The virtual peer rejected the three-byte `00 05 ff` and stopped. This subsequent request is consistent with nPM ADC interrupt enable-clear register, but the state change is not reported as executed. CPU stop PC is 0x58236c for stock 2.4 and 0x57b014 for stock 2.3/CFW. Even at the same IOM function PC, actual execution path and request differ from the earlier stage.

## Verification and limits

The 31 checks in `pmic-restore-unit-01/report.json` verified the exact five queries, unsupported inputs, state preservation on rejection, history boundaries, copies, reset, and explicit profile. `pmic-restore-main-01/report.json` contains the three actual original results. The 77 checks in saved audit `pmic-restore-verification-01/report.json` compared raw logs/markers, pinned inputs, source/board differences, observation order, actual RAM, subsequent writes, identical stock 2.3/CFW model/runtime, and source blob/reset definitions.

Two additional driver files were preserved in a separate npm-restore research folder. Two entries added during download to an existing research manifest were removed to restore its previous list. The manifest's pre-edit byte SHA was not separately recorded; only the restored hash and connection to a separate extension manifest were verified. Existing source files were unchanged.

Order, snapshot contents, and next-request checks requested by independent GPT-6-family review were included in the final audit. Review was source-read-only; the parent separately checked the three native results. Astra and a separate transcript archive review were not used.

This completes one PMIC restore-function path, not full PMIC hardware initialization, G2 boot, or display success. UART TX, ISR, and CQ pairs are 0. Existing virtual SKU/GPU consistency issues remain. Product completion remains 13/29. Next investigate original subsequent interrupt enable/clear initialization and how its state connects to actual GPIO/IRQ. Do not supply generic 0 for unsupported sensor values.
