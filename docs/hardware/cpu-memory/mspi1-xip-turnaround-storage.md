# XIP Turnaround Storage Model

Task bw-0169. Expanded source-supported configuration storage. Overall product completion criteria remained 13/29 (44.8%); web installation, recovery, full boot, and integrated display were incomplete.

## Contract and change

The next request in all three originals, DEV0XIP=`205ED`, changes only bit 17 from stored value `5ED`. In the public Apollo510 SVD/header, XIPTURNAROUND0 is [19:14], and its new value is 8. XIPENTURN bit 5 is set. The pinned HAL also places `ui8TurnAround` in this field. Do not convert 8 into measured latency or arbitrary microseconds.

`inspect_mspi1_xip_turnaround.py` used 24 checks to compare the SVD/header, HAL hash/Git blob, original main, saved markers, store instruction, and attempted write. The evidence is HAL commit `61b293a49db34030c545f99101f7ebf6a3050314` and existing pinned sources.

Added `xipTurnaroundStorage`, default false, to `BlackwallMspi1ConfigStorage`. The new path is used only when existing XIP enable remains set and changed bits are within `FC000` (turnaround). It checks the same power/clock and read-only 32 MiB AXI configuration and updates the value and storage count. It does not increment the XIP enable request count. Source-reset and existing disabled-state storage/disable policies remain.

Requests to change the field simultaneously with initial enable, or to change another field while active, are rejected, as are changes with clock off or PIO busy. The entire XIP module window remains an unknown guard; the model neither fills backing storage nor supplies data through address decoding.

## Verification

- unit01: red phase; platform load failed because the new constructor option did not exist.
- `mspi1-xip-turnaround-unit-02`: 39 passed. The existing 26 XIP and 13 new checks covered values 8/63/0; rejection of format/latency/reserved changes, clock off, and PIO busy; reset; and rejection of unknown bytes.
- `mspi1-xip-turnaround-main-01`: original stock 2.4, 2.3, and Faceclaw plus option-false control, four conditions. Original main, vectors, and existing execution policies were retained.
- All three originals stored turnaround once, ending at `205ED`, with 37 config reads/49 writes. They then stopped attempting to write `200ED` to the same DEV0XIP. PCs were stock 2.4=`4E683A`, stock 2.3/Faceclaw=`4D9466`. Aperture accesses were 0; no flash data was read.
- The option-false control retained the prior `205ED` write/PC `4E75D6` boundary. The 2.3/CFW model, board, and runtime used the same conditions except for main length.

The next request, `205ED` → `200ED`, changes XIPMIXED field 5 → 0. The following stage must check the source contract for that mode and the original caller's purpose. This turnaround option did not automatically permit it.

This model stores controller configuration; it does not verify actual bus turnaround, NOR data, or XIP instruction fetch. Earlier assumptions about idle NOR reset, chip revision, power-ready, ADC, and timing remain. There was no physical glasses connection, flash, or persistent write.

`mspi1-xip-turnaround-regressions-01` reran existing PIO 26 and XIP 26 against the current combined source; all 52 passed. The 59 checks in `mspi1-xip-turnaround-verification-01` compared current source, unit driver, board, original bytes, derived hashes, markers, next guard, zero aperture accesses, default control, equal 2.3/CFW conditions, and regressions.

A review inheriting the parent model found no additional material issues. It distinguished the work from actual bus timing, NOR reads, and XIP execution. No Astra, other model-family review, or full transcript audit was performed.
