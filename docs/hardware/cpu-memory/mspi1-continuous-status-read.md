# Logical Repeated RDSR Model After Retention Restoration

## Confirmed frame and remaining assumptions

After [XIP state restoration](mspi1-xip-retention-restore.md), the original requested status with instruction `05`, CTRL `10441`, and DEV0CFG `01010861`. CTRL selects instruction transmission, one-byte RX, and eight-clock turnaround, without an address phase. DEV0CFG is serial 0/I8/clock divider 1/mode 0; TXNEG/RXNEG/RXCAP are the three sampling bits. The existing status profile accepted only fixed `3010061` with SEPIO 1 and turnaround 0.

`inspect_mspi1_restored_status.py` compared pinned SVD/header, three original main byte sequences, prior native logs, and status helper/stack in 33 conditions. Results are in `simulator/mspi1-restored-status-contract-02/report.json`. The original status helper passes instruction 05 and receive length 1 for bit-0 checks and polling.

Directly inspected a rendered page 32 Figure 25 of the manufacturer MX25U25643G v1.1 PDF (SHA-256 `1488ab399222ab2040e3c56fe8ba8b3ba624f19485a66c7b3558207167be2ae5`). It depicts continuous output of status bytes while CS remains low. Accordingly, constructed a **logical stream model** where the controller consumes the first byte during eight turnaround clocks and reads the next byte. The original PDF and render are preserved outside Git in `mspi1-pio-research-01` and `mspi1-restored-status-contract-01`.

Important limit: the current original uses SEPIO 0. The SVD describes setting SEPIO for devices with separate MOSI/MISO. Actual G2 pin routing and whether this setting is suitable remain unknown. The repeated-status diagram or ideal sampling does not resolve this physical connection issue. Results below explicitly retain this caveat as a logical transport assumption; they do not prove correct data reception on actual hardware.

## Model boundary

`continuousStatusRead` in `BlackwallMspi1PioReset` defaults to false. Selection requires MX identity, a known status seed, and `ideal-sdr`. The new form attaches only to exact CTRL `10441`/instruction `05` and CFG `00010861` excluding the three sampling bits. Reserved forms, other lengths, other opcodes, and arbitrary CFG values are not allowed. The existing fixed status profile remains.

Only on completion is the next repeated status byte placed in FIFO and `ContinuousStatusTransfers` and `StatusDiscardedBytes` each incremented by 1. These are logical byte counts calculated by the model, not actual SPI clock outputs or waveform measurements. The existing 10 µs completion-timer assumption remains. Actual bitstream, pin mux, electrical signals, and timing calibration were not implemented.

Busy, unread FIFO, NOR recovery, and existing ready/clock conditions remain in force. A clock-change abort or `completeTransactions=false` produces no data or discard. Controller-only off preserves accumulated diagnostic history; full Reset clears it. Fixed busy seed 41 remains an always-busy fault input, not an implementation of actual program/erase behavior.

## Original execution results

| Condition | Observation | Next strict request |
| --- | --- | --- |
| Stock 2.4 / opt-in | One new RDSR, original byte `40` → result 0 → poll 0 | PC `4e8a46`, CTRL `100461` / instruction `6c` / address `01fc0000` |
| Stock 2.3 / opt-in | Same | PC `4db672`, same request |
| Faceclaw 38 / opt-in | Same | PC `4db672`, same request |
| Stock 2.4 / default | Zero new RDSR | Blocked at prior CTRL `10441` |
| Stock 2.4 / power stuck-on | Zero new RDSR | Blocked at prior power enable `8400` |

The next request is a 16-byte external NOR read. It stops in the same generic PIO function, so PC is unchanged but instruction, length, and address have changed. No data or completion was supplied for this array request. Each of the three success paths had 1,164 PIO starts/completions, 1,159 FIFO operations, and five status operations including one new form. NOR WEL false, four-byte mode, and existing status `40` were retained.

The previous 355 events were preserved unchanged; three status-byte/result/poll-return events were added for 358, with zero drops. Status-byte observation used R0=`40`; result and poll used R0=0. An existing pinned stack snapshot address was not generalized as the new call's receive-buffer address. Each main matched its pinned bundle byte for byte; original branches, return values, and delays were not forcibly changed. Existing synthetic memory/identity/power assumptions continue to apply.

Final artifacts are outside Git:

- `simulator/mspi1-continuous-status-main-01/`: input SHA, logs, and reports for five original conditions.
- `mspi1-continuous-status-unit-03` and `busy-unit-03`: 44 conditions each. Checked all sampling combinations, incomplete at 5 µs, invalid geometry, unread guard, abort, preservation of nonzero diagnostic history across controller off/on, and full Reset.
- `disabled-unit-01` and `stuck-unit-01`: four conditions each. Their common path-name prefix is `mspi1-continuous-status-`.
- WRDI regression 01's 23 conditions and XIP regression 01's 39 conditions make 158 unit/regression conditions in total.
- `simulator/mspi1-continuous-status-verification-01/report.json`: 105 checks comparing current model, native logs/reports, original bytes, derived SHA, prefix, status results, array rejection, and NOR state.

Also preserved constructor failure `red-01` for an unimplemented API, `unit-01` before 5 µs verification, and `unit-02` before history-preservation strengthening. Failures and historical tests are not reclassified as final hardware success. A read-only review by an agent inheriting the parent model suggested additional history-preservation coverage, which was added; no additional material defects were reported. Astra and a full conversation audit were not used.

## Next investigation

The later [NOR KVDB region investigation](nor-kvdb-region-contract.md) compared partition and header consumer code. The following records questions remaining when the status work ended.

Confirm the actual lane/address contract for instruction 6c and the purpose and data provenance of region `01fc0000`. Distinguish official bundle components, filesystems, and possible per-device content; do not fill zeros without evidence to advance execution. Even when using legitimately obtained data or an explicit initial flash state, do not claim it is identical to an original device dump.

Full boot, integrated display, and physical installation/recovery remained incomplete. Product completion stayed 13/29, 44.8%. There was no glasses connection, scan, RAM payload, flash, OTA, or MRAM write.
