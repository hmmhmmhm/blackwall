# MSPI0 Queue/DMA Completion and Original IRQ Path

bw-0316. Analyzed the completion-handling contract following bw315's nine actual descriptors. Peripheral models and the natural M55 main endpoint remained unchanged. There were zero new native main executions or physical device accesses.

## Original IRQ20 connection

The original vector table's IRQ20 handler reads a registered object and calls the uLED dispatcher. The dispatcher queries INTSTAT using the actual MSPI handle, clears the same value, then runs HAL interrupt service. Registered callback, context, and semaphore were traced through actual main SRAM and read-only tables.

Stock 2.4 connects IRQ entry `4edfc0` → registered dispatcher `5bb578` → HAL service → callback `5c0ab6`. The callback stores the passed status in context and calls the actual semaphore-give function. Older stock and Faceclaw were checked through their own original tables/pointers for equivalent roles.

This test supplies saved full SRAM and **explicit post-enable/IRQ20 context and completion-register fixtures** to Unicorn M7. It does not claim to model actual exception entry, stack frames, NVIC, or DMA execution. Original callback execution was not replaced by a stub.

## Why the completion index matters

The actual posted request has software current 0 and posted 1. HAL reads hardware CURIDX and CQADDR/CQSTAT and handles callbacks for completed requests.

| Declared input | Original handling result |
| --- | --- |
| CURIDX 0, status 0 | No callback; pending 1 and semaphore 0 remain |
| CURIDX 0, raw DMA complete `40` | No callback; pending 1 remains |
| CURIDX 0, CQ update `200` | No callback; pending 1 remains |
| CURIDX 0, CQ paused `400` | No callback; pending 1 remains |
| CURIDX 1, CQ update `200` | Callback status 0, pending 0, semaphore 1 |
| CURIDX 1, combined `640` | Callback status 0, pending 0, semaphore 1 |
| CURIDX 0, DERR `80` / CQERR `800` / SCRERR `1000` | Confirmed up to callback status-1 call boundary |
| CURIDX 0, CQSTAT error | Confirmed up to callback status-1 call boundary |
| CURIDX 0, APBDMAERR `2000` alone | No callback in this original error-mask path |

Some raw-status inputs would not raise IRQ under the current INTEN mask. The checker separately records `hardware_irq_mask_would_assert`. The test call itself is not evidence that a physical IRQ occurred. Do not interpret the APB-error observation as a guarantee of full error recovery.

The success path ran through callback status storage, actual semaphore give, callback-slot removal, software CQ disable, CQCFG 3 → 2 and DMACFG 0 storage, and IRQ-handler return. The error path stopped at callback entry. **Reset, resumption, and recovery after error were not yet executed or verified.**

IRQ masks were checked against names and pinned headers: DCMP=`40`, DERR=`80`, CQUPD=`200`, CQPAUSED=`400`, CQERR=`800`, SCRERR=`1000`, APBDMAERR=`2000`. Current INTEN=`1a80` selects CQUPD and three error types, not DCMP/CQPAUSED themselves. Do not apply bit positions from another similarly named peripheral.

## Test counts and observation controls

Three originals × 11 states × callback observation on/off = **66 IRQ ARM scenarios**. Each pair matched in full PC trace, SRAM, WORK, general registers, XPSR, PRIMASK, and MMIO records. No SRAM memory-write hook was used. Reuses prior bw315 checks internally and separately executes 12 enable-tail ARM scenarios.

Not synthesizing a success callback in pending state and actual DMA completion generating an interrupt are different verifications. The latter remains for the next Renode model work.

## Pause and DMA serialization material

Printed pages 100–102 of the [Apollo4 Programmer's Guide 7.0](https://ambiq.com/wp-content/uploads/2022/10/Apollo4-Family-Programmers-Guide.pdf) describe MSPI queue address-bit-0 interrupts, pause masks, and queue waiting during a transfer block. Saved the local original PDF, rendered the relevant pages, and inspected them directly. This is **design evidence from another chip generation**, not physical Apollo510 proof.

The detailed CQ description in the [Apollo510 datasheet 1.1.0](https://contentportal.ambiq.com/documents/20123/2877485/Apollo510-SoC-Datasheet.pdf/6f7b4ae1-6630-d80c-1e17-ec7445b0509e?download=true&t=1780184793760) is in the IOM section. Do not copy that section's OR pause structure and bit-15 index into MSPI's mask and bit-14 index. Detailed MSPI register definitions refer readers to the SDK.

Pinned Apollo510 SVD and Apollo4 documentation describe matching all designated mask conditions, but pinned Apollo510 HAL uses SWFLAG7 set to unpause and clear to pause. General software-pause polarity remains unknown. The actual first queue writes `4080` with SWFLAG7=1 and current≠end, then changes it to `4000`. Limited behavior that requires no generalization can be connected for this input first. Do not treat other mask/flag combinations as the same success path.

The structure requiring the disable descriptor after DMA start to execute only after the full transfer matches older MSPI documentation and current HAL order. Exact Apollo510 bus timing, chunking, and wire instruction/address format remain unverified. Do not arbitrarily omit 153,602 bytes and update the index.

## Next implementation and preservation

Next build an optional MSPI0 CQ/DMA model. Fetch descriptors from actual SRAM, validate supported pause conditions, address, and length, then defer subsequent fetch while DMA consumes payload. After transfer completion, handle disable, status flags, index update/IRQ in order; retain separate results for incomplete/invalid descriptors and power/clock interruption. Timing must be a virtual service hypothesis distinct from physical measurements.

`tools/inspect_mspi0_dma_completion.py` and private `mspi0-cq-dma-completion-source-03` are the final analysis. Frozen reproduction, source, documents, upstream PDF, and existing model hashes are recorded in `mspi0-cq-dma-completion-verification-01/manifest.json`. Initial exploration's IRQ name/bit guesses were corrected against pinned headers and actual original error masks; the final tool checks the mapping. A failure from trying to read a callback object in a read-only table with an SRAM-only reader remains in diagnostics.

Overall criteria stayed 13/29 = 44.8%, scope v2. The overall goal of web installation, recovery boot, CFW, integrated simulator, and display remained in progress. There was no flash, OTA, persistent write, commit, or external publication.
