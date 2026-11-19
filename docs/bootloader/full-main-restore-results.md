# Virtual full-main restoration and reset results

2026-11-17 · bw-0564/0565. Follow-up to BV08/BV10 of [12 bootloader validation conditions](bootloader-validation-plan.md). The [progress JSON](../data/bootloader-validation-progress.json) governs overall assessment; completion of the execution stages below is not presented as complete recovery.

## Path under test

The compiled context wrapper/RAM writer/callback/stock MRAM adapter of the existing 2.4 research patch are used. This is the existing contract moving a RAM-call entry captured after authentication/upload in an isolated Unicorn worker to M55, not natural creation of UART2 worker from actual boot reset. ROM programming and some GPIO/time/IRQ functions are explicit functional models; original ROM does not execute.

New full-main option permits only body 438010/3,700,064 bytes and vector 438000/16 bytes. Existing default 512-byte test and maximum 4096-byte limit remain. Direct CPU writes to boot/metadata remain blocked. New-scope C# boundary tests and actual ARM transfer results are recorded below.

Stock 2.4 main is 3,700,068 bytes, SHA `df8cfddf3bd29a8351129a8364a8e0dafb347ffc7bfcbca5b52fdd973a7cce4a`. The body's final 12 padding bytes come from pre-modification **virtual** MRAM, not an assumption that physical device tail is zero. After body transfer, original writer per-block readback/response verification, and full MRAM comparison, a separate RAM call writes vector 16 bytes. Actual final full MRAM and full main SHA are checked. No claim is made that original host `Recovery.install` and the separate checksum ARM utility were executed in full.

For reboot, a new frozen board is created after verifying writer-output 4 MiB MRAM hash and boot/main/metadata. Complete boot/main mapping areas come from actual output, and OTA marker owner is pinned to read the actual output word. Main is not reloaded from canonical file, nor runtime PC/branches/SRAM changed to manufacture restoration success. Existing canonical runner SHA gate is not weakened.

## First actual full restore: marker 0

`private:simulator/full-main-restore-bw564-01` passed both actual M55 body and vector calls. Final full main SHA matched stock and full MRAM was unchanged outside specified write ranges. Final MRAM SHA was `1239118e5114e7fe5f6cafa77b9dc849b28617182c60a16688b0fbf0c3683d27`.

`full-main-restored-screen-bw564-01` using that result naturally entered patched boot reset→stock handoff→main reset, but **display failed**. Synthetic initial MRAM marker was 0; original main 44ac86/44ac8a called setter `483708(FFFFFFFF)`. Existing-value comparison at setter 48375e–483762 differed, so it proceeded to storage and the frozen model stopped at original ROM power enable 494ada's 40021014=3f. CFSR/HFSR/policy violations 0, MMIO guard 1. This is not interpreted as ROM or physical recovery success.

Records: first native original log, `boot-reset.json`, failure `report.json`, and `marker-clear-disassembly.txt`. Collector was strengthened to retain failure reports even when a stop produces no cadence/frame dump. Marker was not arbitrarily changed after restoration to turn this result into success.

## Separate initial-state control: marker FFFFFFFF

Existing stock24 original boot→screen profile assumes cleared-marker FFFFFFFF. A separate control explicitly puts that same state in the **pre-restoration baseline**. `full-main-cleared-baseline-bw564-01/manifest.json` records previous baseline, full SHA, four-byte change, and virtual initial condition. Full ARM body/vector transfer was rerun from it and all final states compared again.

Passing this control does not resolve marker 0's ROM boundary. Natural recovery authentication and full-stock/boot self-restoration, actual device factory metadata, Boot ROM, and physical power interruption remain separately unverified.

## Reset assessment after interruption

Actual final MRAM after 0/4/64/68-word interruption is supplied to a fresh boot reset. Actual rejected/accepted→handoff→main event order after the first SP predicate is checked. Because `42e1f6` may be observed even before SP check, rejection is not determined from hit count alone.

A fault fixture retaining only the stock main's existing 16-byte valid vector with a damaged body is also checked. Do not assume vector-last alone prevents entry to a partial image. This deliberately corrupted virtual input is not a direct measurement of actual OTA or a particular CFW failure state.

## Final results and remaining scope

| Virtual initial state/experiment | Actual result | Judgment |
| --- | --- | --- |
| Marker 0, full restoration | Full stock main SHA match→boot/main entry→unsupported ROM power at main marker-clear | Display/full-startup failure retained |
| Marker FFFFFFFF, full restoration | Original M55 writer body 3,700,064 bytes→vector 16 bytes→full main SHA→fresh boot reset→stock main/UI→576×288 guest frame | BV10 complete, limited to this initial state/virtual model |
| Vector 0, interruption at 0/16/256/272 bytes | Actual MRAM prefix passed to fresh reset→rejected branch after SP predicate, handoff/main 0 | BV08 selection path confirmed; later CPD idle unsupported in model |
| Existing stock 16-byte vector retained, interruption at 272 body bytes | Fresh reset→SP accepted→handoff→main reset, body incomplete | Vector-last alone does not prevent partial-image entry |

Cleared control final MRAM SHA is `3e5f340ef2ae006f60bbd476670a38f0ff1a45fbedff805b481a7cbfd4d9ede4`. Main reconstructed from actual writer-output MRAM matches stock SHA df8cfddf…; boot/metadata/neighbors and 12-byte tail also remained as expected. ARM body call had 14,454 ROM/stock-adapter calls; vector call had one. Every call passed context/general/special/floating-point register restoration contract. These are **virtual ROM model** call counts.

Post-restoration raw screen 165,888-byte SHA is `81200ab102c507de6a5853a33086958d16bcb93168ff631ee76b6c8c391adba2`, matching two previous stock boots. It is byte-identical to actual guest SRAM frame source, and raw and separate contrast-enhanced PNG were directly inspected. It shows an 08:00 clock and “No news available / Add new sources in the app” panel. Low brightness of the first fade-in frame remains in raw; contrast preview is not a physical display measurement.

Acceptance complete at this point was **7/12=58.3%**, with BV08/BV10 added. Remaining: BV02 original ROM update path, BV05/06 same-board UART2 authentication/recovery→main, BV11 full-stock restoration of all modified persistent areas, and BV12 complete version combinations. Boot remains a research patch, so BV10 is not called full stock. Marker 0's actual main-startup ROM boundary also remains.

## Evidence, verification, and cleanup

Retained under private simulator:

- `full-main-restore-bw564-02`: initial capture, body/vector native source/logs/manifest, actual final MRAM/main hashes and lineage.
- `full-main-restored-screen-bw564-02`: original boot/reset/context/wire/frame records, actual guest SRAM source and raw/PNG.
- `restore-interruption-reset-bw565-01`: five actual ARM interruption→fresh-reset records, prefixes, reconstructed hashes, and branch order.
- `full-restore-policy-bw564-02`: actual C# component verification of existing policy 23 + full scope 11 + Program rejection 8, distinct from original ARM execution counts.
- `full-main-restore-audit-bw564-03`: independent 52-condition audit preserving source, rerun after cleanup with all passing. Initial 52-condition analysis/packaging history is in 01/02.

Sixteen related host tests (permissions 3, capture 7, reboot input/branch 6) also passed. These are different verification layers; progress is not raised by simply summing their counts.

Removal of 18 owned native jobs and empty Docker run list were confirmed. Duplicate MRAM/SRAM/payload/temporary images totaling 185,490,332 bytes were removed, retaining references, SHAs, and reconstruction rules. Source/proprietary originals, unique initial/final snapshots, inputs directly used by independent audits, and major logs remain. cleanup-summary.json is in audit 03. An inefficient conversion in a separate contrast-preview helper was stopped only in its owned process and corrected without restarting native execution.

## Reproduction commands

From repository root, existing private originals and pinned Renode image are required. Use new output names. These tools perform no serial/BLE/physical installation.

```sh
bw_assets="$HOME/Library/Application Support/Blackwall"
"$bw_assets/simulator/venv-02/bin/python" -B tools/run_full_main_restore.py "$bw_assets/simulator/full-main-new-01" --baseline "$bw_assets/simulator/full-main-cleared-baseline-bw564-01/mram.bin"
python3 -B tools/run_restored_boot.py "$bw_assets/simulator/full-main-new-01/vector" "$bw_assets/simulator/full-main-new-screen-01" --mode restored --screen
"$bw_assets/simulator/venv-02/bin/python" -B tools/run_restore_interruption_matrix.py "$bw_assets/simulator/full-main-new-01" "$bw_assets/simulator/full-main-new-cuts-01"
```

To rerun only the independent audit of existing evidence, specify a new audit output. Evidence needed by final audit was not cleaned up.

```sh
python3 -B tools/audit_full_main_restore.py "$bw_assets/simulator/full-main-restore-bw564-02" "$bw_assets/simulator/full-main-restored-screen-bw564-02" "$bw_assets/simulator/restore-interruption-reset-bw565-01" "$bw_assets/simulator/full-main-audit-new-01"
```

Independent saved execution confirmation (bw-0566): four helpers were also SHA-frozen and audit 04's `audit-source.py` executed in `/tmp` outside repo. Audit 05 passed the same 52 conditions. Actual command, cwd, and source SHA are retained in 05/replay-command.json. No new native run or progress increase occurred.
