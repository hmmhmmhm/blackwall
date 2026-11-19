# MSPI0 Diagnostic RX Model and DMA Frame Export

bw-0319. Connected the four-byte diagnostic read contract identified in bw318 as an explicit fixture. Original main from stock 2.4, 2.3, and Faceclaw each read the response once from FIFO and advanced through **two DMA transfers**. The normal boundary at that point was an unimplemented IOM4 I²C CMD write. Actual device ID, full boot, UI, and panel output were not verified.

## Optional diagnostic response

`diagnosticRxHex` in `BlackwallMspi0Tx` defaults to an empty string, retaining RX rejection. Explicitly specifying four bytes supports only the confirmed `9f`, RX four bytes, CTRL=`40441`, SERIAL0, SDR, ordinary PIO conditions. It does not treat new opcodes or arbitrary identity negotiation as successful.

`12345678` used in execution is **virtual diagnostic data** chosen by us, not an ID extracted from an actual device or stock image. The bw318 original function checks transfer success and uses bytes 1/2 for a log or optional output; the current caller's output pointer is null. Distinguish this virtual input from actual device identification.

Data and completion do not appear immediately at transfer start. After the virtual timer's first 1 µs service, one RX FIFO word is supplied. FIFO read delivers a little-endian word once and removes the entry. An unread word prevents overwriting with a new command or powering down. Completion/incompletion and TX/RX history have separate counters/frames.

With `completeReceive=false`, data can be read but controller completion, success IRQ, and completed frame are not created. Power/clock changes interrupt in-progress reception; RX abort is distinguished from TX abort. This time is not a physical SPI speed or response-latency measurement.

## Original main results

| Condition | Result confirmed |
| --- | --- |
| Stock 2.4/2.3/Faceclaw, `12345678` | One RX start/completion/read each, four bytes delivered, zero aborts. Two DMA/18 descriptors/307,204 bytes; 29 PIO/logical 17 bytes. |
| Stock 2.4, `a55ac33c` | Actually read different diagnostic data once and advanced to the same DMA/PIO counts and IOM4 boundary. |
| Stock 2.4, completion suppressed | One four-byte read but zero RX completions/frames. Stopped at GPIO117 read boundary. |
| RX-disabled control | Matched bw317 CPU, all observation events, and selected events; retained existing RX-start boundary. |

Normal IOM4 boundary is `40054120=101`, original `str.w r2,[r0,#120]`. PCs are stock 2.4 `58236c`, stock 2.3/Faceclaw `57b014`. This CMD is a one-byte WRITE; it did not start because there was no counterpart I²C peer. In bw320, comparing CMD offset `120` with CQCFG offset `228` corrected the earlier CQ label.

The completion-suppressed condition stopped at `40010410` GPIO RD3 read (PC=`501676`, GPIO117). Another task reached this boundary; that does not establish full RX timeout, safe fallback, or completed recovery.

Both normal DMA frames are 153,602 bytes, currently all zero. Each consumed payload hash matches the existing clear buffer and SRAM after stop. Do not extend this to claim natural main drew a nonzero UI. Prior mocked BLE initialization of 59 commands/60 responses also remained.

## Pixel preview of an actual capture

`tools/export_mspi0_frame.py` checks the saved semantic audit, main/capture hashes, and bw318 pixel-layout contract. It exports BIN/PNG/report only when the completed DMA frame's SHA-256 matches bytes in source SRAM after stop. If the buffer changed after transfer, it rejects rather than drawing current SRAM as a historical frame. A separate retained payload capture is required in that case.

```sh
simulator_root='/absolute/path/to/private/simulator'
"$simulator_root/venv-02/bin/python" tools/export_mspi0_frame.py \
  "$simulator_root" \
  "$simulator_root/mspi0-rx-main-01/stock24" \
  "$simulator_root/mspi0-rx-saved-audit-01/stock24/report.json" \
  "$simulator_root/new-frame-preview" --frame 1
```

The verified CPU pixel plane is 640×480, stride 320, high/low nibble order. Using this layout, exported pixels of the actual second DMA and opened the PNG directly. The result is currently a black initialization frame. The viewer's grayscale convention is not evidence of physical brightness/orientation/resolution or correspondence with the 576×288 logical HUD. The bw318 nonzero test pattern is a separate original M7 function test, distinct from this native main frame.

## Checks and preservation

- RX unit 30 and frozen 30: virtual-time reception, one FIFO consumption, unread protection, rejection of other commands, completion suppression, clock interruption, power/reset history, and invalid fixture inputs. These use a synthetic spin program and are not counted as original-main executions.
- Existing DMA 77, TX 45, retention 24, MSPI0 config 33, and existing MSPI1 CQ 33 regressions passed.
- Checked six actual native runs (three normal, one different input, one incomplete, one control) and six saved audits. Initial raw reports' provisional boundary-kind failures were preserved; only semantic contracts were settled through saved audits.
- Passed two frame-exporter checks and two frozen checks for actual byte match and rejection of changes, range errors, and unverified settings.
- `tools/inspect_mspi0_rx_profiles.py` checks main/memory/model capture pins, actual RX read, frames, subsequent DMA/PIO, and original boundary. Original/frozen reports and two inspectors are byte-identical; actual viewer report/exporter/BIN/PNG, four artifacts, are also byte-identical.
- Froze 105 Python dependencies and separate test source. Only one config file changed among nine models. Assets and results are in private `simulator/mspi0-rx-verification-01/manifest.json`.

First red was the unimplemented RX constructor option; exporter red was an unimplemented module. Controls and failure conditions were not removed, and original function PC, branches, and returns were not changed. No actual device was scanned or connected.

## Next work

Before simply allowing IOM4 CMD, analyze the counterpart device's initial transaction together with response consumption. In parallel, use the verified pixel plane and native DMA frame to trace an actual-main nonzero draw path and 576×288 conversion. Do not replace full boot/UI success criteria with the black initialization preview.

Overall scope v2 was 13/29 = 44.8%. The overall goal of web installation, Faceclaw CFW, recovery boot, development simulator, and display continued. No flash, OTA, persistent write, commit, or external publication occurred.

Follow-up correction (bw320): the earlier label “IOM4 CQ enable” was wrong. Address, value, and capture results are unchanged; it denotes the first polling I²C write. Earlier wording was preserved in private research assets.
