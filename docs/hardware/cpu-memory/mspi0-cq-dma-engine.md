# MSPI0 CQ Fetch and Logical DMA Engine

bw-0317. Actual SRAM descriptor fetch and DMA payload consumption were connected to the optional MSPI0 model. Stock 2.4, stock 2.3, and Faceclaw, each run from the original main reset, consumed **9 descriptors, 1 DMA transfer, and 153,602 bytes**. They then progressed through 28 PIO transfers before stopping at an unsupported RX request. Full boot, app UI, and panel output remain incomplete.

## Model behavior and scope

The explicit `queueDma` option in `tools/renode-mspi1-config.cs` must be selected. It reuses the existing TX and retention power, IRQ, and clock owners; the option is disabled by default.

1. Validate the CQEN write and fetch SRAM address/value pairs one at a time using a timer.
2. Check supported pause masks and indices. The current scope is index mask `4000` and the first preamble `4080` with SWFLAG7=1. This does not claim to implement general software pause polarity.
3. Consume actual DMA source, device address, length, and enable descriptors. Source and queue fetches are limited to mapped G2 SRAM; arbitrary writes are not forwarded to external MMIO.
4. Defer subsequent descriptor fetches during DMA and read payload in chunks from source SRAM. Record the frame and set DMA complete pending only after completion.
5. Execute the subsequent disable, set-clear0, and CURIDX update descriptors. Treat bit 0 of a descriptor address as a CQ update IRQ request rather than issuing an unaligned CPU write.
6. Pause the queue when the index equals end. The guest can clear the IRQ and disable the queue.

Virtual service time is 1 µs per descriptor and at most 256 bytes/µs for DMA payload. **These figures do not reproduce physical SPI speed, latency, or FPS.** This is a functional model for checking transferred data and controller event order. It records DMA payload and configuration metadata, but does not implement the actual instruction/address/payload wire bitstream or external slave reception and state changes.

The supported DMA profile is normal or D4 SERIAL0-based SDR, M2P, priority 1, and HW enable 3. The actual main configuration is DEV0CFG=`40161`, CTRL1=`5`, DEV0XIP=`45ec`, and DEV0INSTR=`630062`. This differs from the initial PIO normal serial configuration. Enable is determined from DMA/XIP enable fields; other configuration bits need not be 0.

One queue activation is limited to 128 fetches and 64 recorded frames totaling 4 MiB. These are simulator resource limits, not hardware maximums. Wrap, arbitrary queue commands, other pause combinations, RX, and reset/restart after an error are not yet supported.

## Successful original main runs

All three originals use payload source `20094400`, device address 0, and length 153,602 bytes. The SHA256 of the consumed payload matches the bw315 **original pre-CQ SRAM buffer** hash. Its current contents are all 0. Similarity between the length and a raw panel size candidate alone does not establish the panel format or a valid viewer image.

| Item | Result for all three images |
| --- | --- |
| CQ descriptors | 9 |
| DMA start / completion / abort | 1 / 1 / 0 |
| Consumed payload | 153,602 bytes, source hash matches |
| Model faults | None |
| Subsequent PIO | 28 starts and 28 completions, 17 logical payload bytes total |
| BLE initialization prefix | Mock command 59 / response 60 retained |

The next boundary is the original PIO RX request with instruction=`9f`, 4 data bytes, and CTRL=`40441`. It stopped on the supported-scope check when the actual `str.w lr,[r2]` attempted a write to `40060000`. The PC is `4e8a46` for stock 2.4 and `4db672` for stock 2.3/Faceclaw. No arbitrary ID or response was supplied to this request.

The queue's pending IRQ output was confirmed in unit tests. Although the original main progressed to the next path, **no dedicated IRQ entry/callback PC observation point was added to this native run**. This is distinct from claiming direct counts of the exact natural IRQ/callback/PendSV path. The bw316 isolated original IRQ/callback test remains separate evidence.

## Incomplete cases, rejection, and control

With `completeDma=false`, stock 2.4 remained DMA active after the first 6 descriptors: 1 start, 0 completions, 0 consumed, 0 frames, and incomplete index. It did not fetch the subsequent disable/index descriptors. Another task reached the IOM4 CMD write boundary (`40054120=101`, PC=`58236c`). This does not establish a complete DMA timeout, safe fallback, or successful recovery.

An invalid source, external MMIO destination, unsupported descriptor, or power/clock interruption is recorded as a model fault and stops engine progress. It creates neither a success IRQ nor a completion index. This is **model rejection**, not a synthesized hardware error IRQ. Other CPU tasks may run to a separate boundary, so a later PC in a faulted capture is not accepted as valid boot progress. Semantic checks also reject faults.

The control run without the option matched the bw314 TX model's CPU, complete observed events, and selected events, retaining the existing CQEN boundary. No actual glasses or case were scanned or connected.

## Checks, failure history, and freeze

- `tools/verify_mspi0_dma.py`: 77 checks on a synthetic spin/SRAM queue. These cover actual source bytes without padding, fetch deferral during DMA, completion index/IRQ, guest ack/disable, power retention, incomplete operation, clock interruption, invalid source/destination, and D4. They are not counted as natural boot runs.
- Frozen DMA 77, existing TX 45, retention 24, MSPI0 configuration 33, and existing MSPI1 CQ 33 regression checks passed.
- Five final native runs (3 successful, 1 incomplete, 1 control) and five saved audits were checked. Including three earlier diagnostic native runs, this work added eight native main runs in total.
- `tools/inspect_mspi0_dma_profiles.py` checks main/capture hashes, memory collection, the original pre-CQ payload hash, configuration metadata, the next actual RX command, and the control. Original and frozen analyses have byte-identical reports and inspectors.
- 100 Python dependencies were frozen; only the config file changed among nine model files. Inputs, outputs, failures, freeze, and hashes are recorded in private `simulator/mspi0-dma-verification-01/manifest.json`.

The first red was an unimplemented constructor option; the D4 red was rejection of an actual mixed profile. Initial unit compilation failed because the timer owner lacked IPeripheral. The first native run incorrectly rejected nonzero configuration on disabled XIP (the enable bit of `45ec` is 0). The next diagnostic rejected D4 after five descriptors under the normal PIO profile condition; a run with a configuration snapshot confirmed CTRL1/XIPMIXED=5. Failed results were not overwritten. The first semantic contract for the final successful run also failed because it fixed TX completions at 4 and did not allow the subsequent 28 transfers; the raw report was preserved and the saved audit checked the actual DMA, PIO, and boundary.

A renewed SVD enum comparison corrected “serial CE1” in the bw314 document to SERIAL0/CS0. The code's DEVCFG0 value 1 check was correct; the wording was wrong.

## Next work

Analyze the RX `9f` caller, response consumption, and failure branches in the original code. Do not supply an unverified device response as a success value. Investigate this path alongside uLED packet/buffer generation rules to connect a meaningful framebuffer and panel transfer. If needed, add a short observation of natural IRQ/callback as a separate control condition.

Overall completion remains 13/29=44.8%, scope v2. The overall goals of web installation, recovery boot, Faceclaw CFW, developer simulator, and display remain in progress; no flash, OTA, permanent write, commit, or external publication was performed.

Subsequent correction (bw320): The IOM4 boundary in this document is CMD (offset 120), not CQCFG. IOM CQCFG is offset 228; collected address, value, and execution results are unchanged. The earlier wording remains in private research assets.
